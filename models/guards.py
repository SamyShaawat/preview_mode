"""Safe-run guards: a preview never commits, sends, calls out or burns a sequence number.

Every guard keys on the per-thread ``_guard.recorder`` that only ``safe_run`` sets,
so other threads and requests that are not a preview are untouched.
"""
import functools
import threading
from contextlib import contextmanager
from urllib.parse import urlsplit

import requests

from odoo import models
from odoo.modules.registry import Registry
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


@contextmanager
def safe_run(env):
    cr = env.cr
    own_commit = cr.__dict__.get('commit')  # a test may already patch it per instance
    postcommit = cr.postcommit
    savepoint = cr.savepoint()
    try:
        with ChangeRecorder() as recorder:
            # Instance attribute: shadows Cursor.commit for this cursor only, no class patch.
            cr.commit = _no_commit
            # Callbacks queued during the preview (mail, bus...) must not run at the real commit.
            cr.postcommit = Callbacks()
            _guard.recorder = recorder
            yield recorder
    finally:
        _guard.recorder = None
        cr.postcommit = postcommit
        if own_commit is None:
            cr.__dict__.pop('commit', None)
        else:
            cr.commit = own_commit
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


def _guarded_cursor(cursor):
    @functools.wraps(cursor)
    def guarded_cursor(self, *args, **kwargs):
        recorder = guarded()
        if recorder is not None:
            # A second cursor could commit behind the savepoint's back.
            recorder.incomplete = True
            recorder.warnings.append('A separate database transaction was needed')
            raise PreviewIncomplete('separate cursor')
        return cursor(self, *args, **kwargs)
    guarded_cursor._preview_guard = True
    return guarded_cursor


guarded_send = None


def install_patches():
    """Called once from post_load. Both patches are inert unless this thread runs a preview."""
    global guarded_send
    # WHY: outgoing HTTP is not transactional; Session.send is the single chokepoint of requests.
    if not getattr(requests.Session.send, '_preview_guard', False):
        requests.Session.send = _guarded_send(requests.Session.send)
    guarded_send = requests.Session.send
    # WHY: a new cursor commits independently of the preview savepoint.
    if not getattr(Registry.cursor, '_preview_guard', False):
        Registry.cursor = _guarded_cursor(Registry.cursor)


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    def _next(self, sequence_date=None):
        # Postgres sequences ignore rollback: never draw a real number in a preview.
        if guarded() is not None:
            return '(new)'
        return super()._next(sequence_date=sequence_date)


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    def _connect__(self, *args, **kwargs):  # noqa: PLW3201 - Odoo 20 name (connect() before)
        if guarded() is not None:
            return None
        return super()._connect__(*args, **kwargs)

    def send_email(self, message, *args, **kwargs):
        recorder = guarded()
        if recorder is None:
            return super().send_email(message, *args, **kwargs)
        recorder.emails.append({
            'to': message['To'] or '',
            'subject': message['Subject'] or '',
        })
        return message['Message-Id']
