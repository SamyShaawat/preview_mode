"""Safe-run guards: a preview never commits, sends, calls out or burns a sequence number.

Every guard keys on the per-thread ``_guard.recorder`` that only ``safe_run`` sets,
so other threads and requests that are not a preview are untouched.
"""
import functools
import http.client
import threading
from contextlib import contextmanager
from urllib.parse import urlsplit

import requests

from odoo import models, sql_db
from odoo.addons.base.models import ir_mail_server
from odoo.tools.misc import Callbacks

from .recorder import ChangeRecorder

_guard = threading.local()


class PreviewBlocked(Exception):
    """An outgoing call was attempted during a preview."""


class PreviewIncomplete(Exception):
    """The previewed code needed something a preview cannot simulate."""


def guarded():
    """The recorder of the preview running in this thread, or None."""
    return getattr(_guard, 'recorder', None)


def _no_commit():
    # The savepoint is the only transaction boundary during a preview.
    pass


def _incomplete(reason):
    recorder = guarded()
    recorder.incomplete = True
    recorder.warnings.append(reason)
    raise PreviewIncomplete(reason)


def _no_rollback():
    # A real rollback would drop the savepoint and the work done before the preview.
    _incomplete('The action rolled back its own transaction')


@contextmanager
def safe_run(env):
    cr = env.cr
    # A test (or an outer safe_run) may already shadow these per instance: put them back after.
    own = {name: cr.__dict__.get(name) for name in ('commit', 'rollback')}
    postcommit = cr.postcommit
    previous = guarded()  # nested run: the outer preview's guards must stay on
    savepoint = cr.savepoint()
    try:
        with ChangeRecorder() as recorder:
            # Instance attributes: shadow Cursor.commit/rollback for this cursor only, no class patch.
            cr.commit = _no_commit
            cr.rollback = _no_rollback
            # Callbacks queued during the preview (mail, bus...) must not run at the real commit.
            cr.postcommit = Callbacks()
            _guard.recorder = recorder
            yield recorder
    finally:
        _guard.recorder = previous
        cr.postcommit = postcommit
        for name, value in own.items():
            if value is None:
                cr.__dict__.pop(name, None)
            else:
                setattr(cr, name, value)
        savepoint.close(rollback=True)


def _guarded_send(send):
    @functools.wraps(send)
    def guarded_send(session, request, **kwargs):
        recorder = guarded()
        if recorder is not None:
            host = urlsplit(request.url).hostname or request.url
            recorder.warnings.append('Blocked a call to %s' % host)
            raise PreviewBlocked(host)
        return send(session, request, **kwargs)
    guarded_send._preview_guard = True
    return guarded_send


def _guarded_connect(connect):
    @functools.wraps(connect)
    def guarded_connect(self, *args, **kwargs):
        recorder = guarded()
        if recorder is not None:
            recorder.warnings.append('Blocked a call to %s' % self.host)
            raise PreviewBlocked(self.host)
        return connect(self, *args, **kwargs)
    guarded_connect._preview_guard = True
    return guarded_connect


def _guarded_cursor(cursor):
    @functools.wraps(cursor)
    def guarded_cursor(self, *args, **kwargs):
        if guarded() is not None:
            # A second cursor could commit behind the savepoint's back.
            _incomplete('A separate database transaction was needed')
        return cursor(self, *args, **kwargs)
    guarded_cursor._preview_guard = True
    return guarded_cursor


guarded_send = None
guarded_http_connect = None


def install_patches():
    """Called once from post_load. All patches are inert unless this thread runs a preview."""
    global guarded_send, guarded_http_connect
    # WHY: outgoing HTTP is not transactional; Session.send is the single chokepoint of requests.
    if not getattr(requests.Session.send, '_preview_guard', False):
        requests.Session.send = _guarded_send(requests.Session.send)
    guarded_send = requests.Session.send
    # WHY: urllib.request.urlopen and raw http.client both open the socket in HTTPConnection.connect
    # (HTTPSConnection.connect calls it too), so one patch covers both; requests is blocked above.
    if not getattr(http.client.HTTPConnection.connect, '_preview_guard', False):
        http.client.HTTPConnection.connect = _guarded_connect(http.client.HTTPConnection.connect)
    guarded_http_connect = http.client.HTTPConnection.connect
    # WHY: a new cursor commits independently of the preview savepoint. Connection.cursor is
    # where Registry.cursor, db_connect(...).cursor() (cron, bus) all meet, before a pool borrow.
    if not getattr(sql_db.Connection.cursor, '_preview_guard', False):
        sql_db.Connection.cursor = _guarded_cursor(sql_db.Connection.cursor)


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    def _next(self, sequence_date=None):
        # Postgres sequences ignore rollback: never draw a real number in a preview.
        if guarded() is not None:
            return '(new)'
        return super()._next(sequence_date=sequence_date)


# The SMTP connect method is `_connect__` on Odoo 19/20 and `connect` on 16 to 18. Class names
# differ too, so find the base model class by _name and detect the name once, no rename per port.
_base_mail = next(c for c in vars(ir_mail_server).values() if getattr(c, '_name', None) == 'ir.mail_server')
_CONNECT = '_connect__' if hasattr(_base_mail, '_connect__') else 'connect'


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    # PORT: none needed, the connect method name is detected (see _CONNECT above).
    def _guarded_connect(self, *args, **kwargs):
        if guarded() is not None:
            return None
        return getattr(super(), _CONNECT)(*args, **kwargs)

    vars()[_CONNECT] = _guarded_connect
    del _guarded_connect

    def send_email(self, message, *args, **kwargs):
        recorder = guarded()
        if recorder is None:
            return super().send_email(message, *args, **kwargs)
        if (message['Subject'] or '') not in recorder.queued_subjects:  # already counted as a mail.mail row
            recorder.emails.append({
                'to': message['To'] or '',
                'subject': message['Subject'] or '',
            })
        return message['Message-Id']
