import http.client
import threading
import urllib.request
from email.message import EmailMessage
from unittest.mock import patch

import requests

from odoo import api, sql_db
from odoo.tests.common import TransactionCase, tagged

from ..models import guards
from ..models.guards import PreviewBlocked, PreviewIncomplete, safe_run


@tagged('post_install', '-at_install')
class TestGuards(TransactionCase):

    def test_rollback_after_run(self):
        with safe_run(self.env):
            self.env['res.partner'].create({'name': 'Preview Rollback'})
        self.assertEqual(self.env['res.partner'].search_count([('name', '=', 'Preview Rollback')]), 0)

    def test_commit_does_not_persist(self):
        # TransactionCase already forbids commit on self.cr: use a real cursor.
        name = 'Preview Commit Guard'
        try:
            with self.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, {})
                with safe_run(env):
                    env['res.partner'].create({'name': name})
                    cr.commit()
            with self.registry.cursor() as cr:
                self.assertEqual(self._count(cr, name), 0)
        finally:
            with self.registry.cursor() as cr:
                cr.execute("DELETE FROM res_partner WHERE name = %s", [name])

    @staticmethod
    def _count(cr, name):
        cr.execute("SELECT count(*) FROM res_partner WHERE name = %s", [name])
        return cr.fetchone()[0]

    def test_sequence_is_placeholder_and_not_consumed(self):
        code = 'preview_mode.test'
        self.env['ir.sequence'].create({'name': 'Preview test', 'code': code, 'prefix': 'PT', 'padding': 3})
        with safe_run(self.env):
            self.assertEqual(self.env['ir.sequence'].next_by_code(code), '(new)')
        self.assertEqual(self.env['ir.sequence'].next_by_code(code), 'PT001')

    def test_email_listed_not_sent(self):
        server = self.env['ir.mail_server']
        message = EmailMessage()  # stdlib: build_email was renamed _build_email__ in 20
        message['From'], message['To'], message['Subject'] = 'a@example.com', 'b@example.com', 'Hello'
        message.set_content('Body')
        with patch('smtplib.SMTP', side_effect=AssertionError('SMTP touched')), \
                patch('smtplib.SMTP_SSL', side_effect=AssertionError('SMTP touched')), \
                safe_run(self.env) as rec:
            server.send_email(message)
        self.assertEqual(len(rec.emails), 1)
        self.assertEqual(rec.emails[0]['subject'], 'Hello')

    def test_http_blocked(self):
        # The test framework replaces Session.send with its own blocker for the
        # whole class, so put back the wrapper post_load installed.
        with patch.object(requests.Session, 'send', guards.guarded_send), safe_run(self.env) as rec:
            with self.assertRaises(PreviewBlocked):
                requests.get('http://example.invalid')
        self.assertTrue(any('example.invalid' in w for w in rec.warnings))

    def test_urllib_and_http_client_blocked(self):
        # Same as above: the framework may replace these, so restore the installed guard.
        with patch.object(http.client.HTTPConnection, 'connect', guards.guarded_http_connect):
            with safe_run(self.env) as rec:
                with self.assertRaises(PreviewBlocked):
                    urllib.request.urlopen('http://example.invalid/')
                with self.assertRaises(PreviewBlocked):
                    http.client.HTTPSConnection('example.invalid').request('GET', '/')
            self.assertEqual(sum('example.invalid' in w for w in rec.warnings), 2)
            # Inert outside a preview and in other threads: the real connect runs (and fails on DNS).
            conn = http.client.HTTPConnection('example.invalid')
            with self.assertRaises(OSError):
                conn.connect()
            errors = []

            def work():
                try:
                    conn.connect()
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

            with safe_run(self.env):
                thread = threading.Thread(target=work)
                thread.start()
                thread.join()
            self.assertTrue(errors and isinstance(errors[0], OSError))

    def test_separate_cursor_marks_incomplete(self):
        with safe_run(self.env) as rec:
            with self.assertRaises(PreviewIncomplete):
                self.registry.cursor()
        self.assertTrue(rec.incomplete)

    def test_exception_clears_every_guard(self):
        cr = self.env.cr
        commit = cr.commit
        postcommit = cr.postcommit
        calls = []
        with self.assertRaises(ZeroDivisionError), safe_run(self.env):
            cr.postcommit.add(lambda: calls.append(1))
            1 / 0
        self.assertIsNone(guards.guarded())
        self.assertEqual(cr.commit, commit)
        self.assertIs(cr.postcommit, postcommit)
        cr.postcommit.run()  # Callbacks.run exists on 16 to 20; __len__ does not
        self.assertEqual(calls, [])
        self.registry.cursor().close()  # cursor guard is off again

    def _message(self):
        message = EmailMessage()
        message['From'], message['To'], message['Subject'] = 'a@example.com', 'b@example.com', 'Nested'
        message.set_content('Body')
        return message

    def test_nested_run_keeps_outer_guards(self):
        with safe_run(self.env) as outer:
            with safe_run(self.env) as inner:
                pass
            self.assertIs(guards.guarded(), outer)
            self.env['ir.mail_server'].send_email(self._message())
        self.assertIsNone(guards.guarded())
        self.assertEqual(len(outer.emails), 1)
        self.assertEqual(inner.emails, [])

    def test_db_connect_cursor_marks_incomplete(self):
        db = sql_db.db_connect(self.env.cr.dbname)
        with safe_run(self.env) as rec:
            with self.assertRaises(PreviewIncomplete):
                db.cursor()
        self.assertTrue(rec.incomplete)
        db.cursor().close()  # outside a preview it works

    def test_other_thread_cursor_unaffected(self):
        db = sql_db.db_connect(self.env.cr.dbname)
        result = []

        def work():
            with db.cursor() as cr:
                cr.execute('SELECT 1')
                result.append(cr.fetchone()[0])

        with safe_run(self.env):
            thread = threading.Thread(target=work)
            thread.start()
            thread.join()
        self.assertEqual(result, [1])

    def test_rollback_marks_incomplete(self):
        name = 'Preview Rollback Guard'
        with self.assertRaises(PreviewIncomplete), safe_run(self.env) as rec:
            self.env['res.partner'].create({'name': name})
            self.env.cr.rollback()
        self.assertTrue(rec.incomplete)
        self.assertEqual(self.env['res.partner'].search_count([('name', '=', name)]), 0)

    def test_connect_guard_blocks_smtp_in_preview_only(self):
        server = self.env['ir.mail_server']
        name = '_connect__' if hasattr(server, '_connect__') else 'connect'  # differs across versions
        base = [c for c in type(server).__mro__ if name in vars(c)][-1]
        # Test mode makes the real method a no-op before SMTP, so stand in for it on the base class:
        # reached outside a preview (returns the marker), never reached inside one.
        with patch('smtplib.SMTP', side_effect=AssertionError('SMTP touched')), \
                patch('smtplib.SMTP_SSL', side_effect=AssertionError('SMTP touched')), \
                patch.object(base, name, return_value='real') as real:
            with safe_run(self.env):
                self.assertIsNone(getattr(server, name)(host='localhost', port=25))
            self.assertFalse(real.called)
            self.assertEqual(getattr(server, name)(host='localhost', port=25), 'real')
