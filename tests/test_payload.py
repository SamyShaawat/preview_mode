from email.message import EmailMessage
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.sql_db import db_connect

from ..models.payload import LOCK_NAMESPACE, MAX_ROWS, _noun, _summary, _timeout, build_preview
from ..models.recorder import ChangeRecorder


@tagged('post_install', '-at_install')
class TestPayload(TransactionCase):
    # create_company does not exist on Odoo 20 and res.partner has no menu with only
    # base/web; `copy` is a real public create-button method and test-only methods are
    # patched onto res.partner for the other cases.

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Preview Co'})
        cls.Partner = type(cls.env['res.partner'])

    def _patch(self, func):
        return patch.object(self.Partner, 'preview_mode_test_button', func, create=True)

    def test_payload_for_create_button(self):
        payload = build_preview(self.env, 'res.partner', 'copy', [self.partner.id], [], {}, 'Create company')
        self.assertEqual(len(payload['changes']), 1, payload)
        row = payload['changes'][0]
        self.assertEqual(row['kind'], 'new')
        self.assertTrue(row['where'])
        self.assertTrue(payload['summary'].startswith('Confirming will create'), payload['summary'])

    def test_payload_empty_for_action_only_button(self):
        def button(self):
            return {'type': 'ir.actions.act_window', 'res_model': 'res.partner'}
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Open')
        self.assertEqual(payload['changes'], [])
        self.assertFalse(payload['warnings'])
        self.assertFalse(payload['show'])

    def test_payload_failure_before_write_is_shown(self):
        def button(self):
            raise UserError('Period locked')
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Post')
        self.assertTrue(payload['show'])
        self.assertEqual(payload['changes'], [])
        self.assertIn({'text': 'Confirming will fail: Period locked', 'blocking': True}, payload['warnings'])
        self.assertEqual(payload['summary'], '')  # the error is shown once, as the warning

    def test_payload_incomplete_is_shown(self):
        def button(self):
            self.env.cr.rollback()
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Go')
        self.assertTrue(payload['incomplete'])
        self.assertTrue(payload['show'])

    def test_payload_email_only_is_shown(self):
        def button(self):
            msg = EmailMessage()
            msg['To'], msg['Subject'] = 'b@example.com', 'Hello'
            self.env['ir.mail_server'].send_email(msg)
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Send')
        self.assertTrue(payload['show'])
        self.assertEqual(payload['changes'], [])
        self.assertEqual(payload['emails'][0]['subject'], 'Hello')

    def test_payload_lists_queued_mail_once(self):
        if 'mail.mail' not in self.env:
            self.skipTest('mail is not installed')

        def button(self):
            mail = self.env['mail.mail'].create({
                'subject': 'Queued hello', 'email_to': 'b@example.com', 'body_html': '<p>Hi</p>'})
            mail.send()  # an immediate send reaches send_email too: still one entry
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Send')
        self.assertTrue(payload['show'])
        self.assertEqual([(e['subject'], e['to']) for e in payload['emails']], [('Queued hello', 'b@example.com')])
        self.assertEqual(payload['changes'], [])
        self.assertIn('queue 1 email', payload['summary'])

    def test_payload_failing_button_is_blocking_warning(self):
        def button(self):
            raise UserError('Period locked')
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Post')
        self.assertIn({'text': 'Confirming will fail: Period locked', 'blocking': True}, payload['warnings'])

    def test_timeout_is_clamped(self):
        ICP = self.env['ir.config_parameter']
        for value, expected in (('0.01', 1), ('-5', 1), ('9999', 120), ('30', 30), ('0', 10)):
            ICP.set_param('preview_mode.timeout', value)
            self.assertEqual(_timeout(self.env), expected, value)

    def test_payload_times_out(self):
        self.env['ir.config_parameter'].set_param('preview_mode.timeout', '1')

        def button(self):
            self.env.cr.execute('SELECT pg_sleep(4)')
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Slow')
        self.assertTrue(payload['incomplete'])
        self.assertTrue(payload['show'])
        self.assertIn('timed out', payload['warnings'][0]['text'])
        # the normal timeout is back and the cursor works again
        self.env.cr.execute('SELECT pg_sleep(1.2)')
        self.assertEqual(self.partner.name, 'Preview Co')

    def test_payload_skips_too_many_records(self):
        ICP = self.env['ir.config_parameter']
        ICP.set_param('preview_mode.max_records', '1')
        payload = build_preview(self.env, 'res.partner', 'copy', [1, 2], [], {}, 'Copy')
        self.assertFalse(payload['show'])
        self.assertIn('Too many records', payload['notice'])

    def test_kill_switch_stops_previews(self):
        self.env['ir.config_parameter'].set_param('preview_mode.enabled', 'False')
        payload = build_preview(self.env, 'res.partner', 'copy', [self.partner.id], [], {}, 'Copy')
        self.assertFalse(payload['show'])
        self.assertIn('switched off', payload['notice'])
        self.assertFalse(self.env['res.partner'].search([('name', '=', 'Preview Co (copy)')]))

    def test_registry_changing_models_are_never_run(self):
        for model in ('ir.module.module', 'res.config.settings', 'base.module.upgrade', 'ir.ui.view'):
            with patch('odoo.addons.preview_mode.models.payload.call_kw') as call_kw:
                payload = build_preview(self.env, model, 'execute', [1], [], {}, 'Go')
            call_kw.assert_not_called()
            self.assertFalse(payload['show'], model)

    def test_payload_shows_recomputed_stored_field(self):
        # complete_name is a stored computed field: it is flushed through _write_multi (_write on 16 and 17), not write().
        def button(self):
            self.name = 'Renamed Co'
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Go')
        fields = {f['label']: (f['old'], f['new']) for row in payload['changes'] for f in row['fields']}
        self.assertEqual(fields.get('Complete Name'), ('Preview Co', 'Renamed Co'), payload)
        self.assertEqual(self.partner.complete_name, 'Preview Co')

    def test_payload_caps_rows(self):
        partners = self.env['res.partner'].create([{'name': 'P%s' % i} for i in range(300)])

        def button(self):
            partners.write({'comment': 'bulk'})
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Bulk')
        self.assertLessEqual(len(payload['changes']), 201)
        self.assertEqual(payload['changes'][-1]['what'], 'and 100 more')

    def test_payload_rolls_back(self):
        def button(self):
            self.write({'name': 'Renamed'})
            self.create({'name': 'Preview ghost'})
        with self._patch(button):
            build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Go')
        self.assertEqual(self.partner.name, 'Preview Co')
        self.assertFalse(self.env['res.partner'].search([('name', '=', 'Preview ghost')]))

    def test_payload_private_method_refused(self):
        with self.assertRaises(AccessError):
            build_preview(self.env, 'res.partner', '_compute_display_name', [self.partner.id], [], {}, 'x')

    def test_payload_invalid_model_refused(self):
        for model in ('no.such.model', 'mail.thread'):  # unknown, abstract
            with self.assertRaisesRegex(AccessError, 'Invalid model'):
                build_preview(self.env, model, 'write', [], [], {}, 'x')

    def test_payload_for_wizard_button(self):
        # A wizard (transient model) button that changes a real record previews like any other.
        def button(wizard, partner_id):
            self.env['res.partner'].browse(partner_id).name = 'Wizard changed'
        Wizard = type(self.env['base.enable.profiling.wizard'])
        wizard = self.env['base.enable.profiling.wizard'].create({})
        with patch.object(Wizard, 'preview_mode_test_button', button, create=True):
            payload = build_preview(self.env, 'base.enable.profiling.wizard', 'preview_mode_test_button',
                                    [wizard.id], [self.partner.id], {}, 'Apply')
        self.assertTrue(payload['show'], payload)
        self.assertEqual(payload['changes'][0]['kind'], 'changed')
        self.assertEqual(self.partner.name, 'Preview Co')

    def test_user_flag_is_self_writable(self):
        user = new_test_user(self.env, 'preview_flag', groups='base.group_user')
        user.with_user(user).write({'preview_mode_enabled': True})
        self.assertTrue(user.preview_mode_enabled)

    def _hold_lock(self, uid):
        cr = db_connect(self.env.cr.dbname).cursor()
        self.addCleanup(cr.close)  # closing rolls back, which releases the lock
        cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (LOCK_NAMESPACE, uid))

    def test_second_preview_of_same_user_is_not_previewed(self):
        self._hold_lock(self.env.uid)
        payload = build_preview(self.env, 'res.partner', 'copy', [self.partner.id], [], {}, 'Copy')
        self.assertFalse(payload['show'])
        self.assertIn('already running', payload['notice'])
        self.assertFalse(payload['changes'])

    def test_other_users_preview_is_not_blocked(self):
        self._hold_lock(new_test_user(self.env, 'preview_lock_other', groups='base.group_user').id)
        payload = build_preview(self.env, 'res.partner', 'copy', [self.partner.id], [], {}, 'Copy')
        self.assertTrue(payload['show'], payload)


@tagged('post_install', '-at_install')
class TestPayloadMerge(TransactionCase):
    def test_merge_one_row_per_record_and_drops_noise(self):
        from ..models.payload import _merge
        from ..models.recorder import Change
        rows = _merge([
            Change('changed', 'res.partner', 1, 'A', [('Name', 'A', 'B')]),
            Change('changed', 'res.partner', 1, 'false', [('Name', 'B', 'C'), ('Note', 'x', 'x')]),
            Change('changed', 'res.partner', 2, 'Z', [('Name', 'Z', 'Z')]),
            Change('new', 'res.partner', 3, 'N', []),
        ])
        self.assertEqual([(r['kind'], r['what']) for r in rows], [('changed', 'A'), ('new', 'N')])
        self.assertEqual(rows[0]['fields'], {'Name': ('A', 'C')})

    def test_payload_mass_archive_and_delete_cover_all_ids(self):
        # List-view mass actions send every selected id; rows are capped at MAX_ROWS.
        partners = self.env['res.partner'].create([{'name': 'Mass %s' % i} for i in range(MAX_ROWS + 5)])
        archive = build_preview(self.env, 'res.partner', 'action_archive', partners.ids, [], {}, 'Archive')
        self.assertTrue(archive['show'])
        self.assertEqual(len(archive['changes']), MAX_ROWS + 1)
        self.assertEqual(archive['changes'][-1]['kind'], 'more')
        self.assertEqual(archive['changes'][-1]['what'], 'and 5 more')
        self.assertTrue(all(partners.mapped('active')), 'the preview must roll back')
        deleted = build_preview(self.env, 'res.partner', 'unlink', partners.ids[:3], [], {}, 'Delete')
        self.assertEqual([c['kind'] for c in deleted['changes']], ['deleted'] * 3)
        self.assertEqual(len(partners[:3].exists()), 3)


@tagged('post_install', '-at_install')
class TestJournal(TransactionCase):
    def test_journal_for_post_button(self):
        if 'account.move' not in self.env:
            self.skipTest('account is not installed')
        partner = self.env['res.partner'].create({'name': 'Vendor X'})
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': partner.id, 'invoice_date': '2026-01-01',
            'invoice_line_ids': [(0, 0, {'name': 'Item', 'quantity': 1, 'price_unit': 100})],
        })
        result = build_preview(self.env, 'account.move', 'action_post', [bill.id], [], {}, 'Confirm')
        self.assertEqual(len(result['journal']), 1)
        self.assertTrue(result['journal'][0]['balanced'])
        self.assertEqual(sum(line['debit'] for line in result['journal'][0]['lines']),
                         sum(line['credit'] for line in result['journal'][0]['lines']))
        self.assertEqual(bill.state, 'draft')

    def test_summary_plurals_and_join(self):
        new, upd, dele = (dict(kind=k, model='res.partner') for k in ('new', 'changed', 'deleted'))
        summary = lambda changes, emails=(): _summary(self.env, changes, emails)  # noqa: E731
        self.assertEqual(summary([]), '')  # zero: nothing to say
        self.assertEqual(summary([upd]), 'Confirming will update 1 contact.')  # singular
        self.assertEqual(summary([upd, upd]), 'Confirming will update 2 contacts.')  # plural
        self.assertEqual(summary([dele], [1]), 'Confirming will delete 1 contact and queue 1 email (not sent during the preview).')
        # zero items omitted, three items joined "A, B and C"
        self.assertEqual(_noun(self.env, 'res.partner.category', 2), 'partner tags')
        self.assertEqual(_noun(self.env, 'res.country', 2), 'countries')
        self.assertEqual(_noun(self.env, 'res.partner', 1), 'contact')
        self.assertEqual(
            summary([new, upd, upd, dele, dele], [1, 2]),
            'Confirming will create 1 contact, update 2 contacts, delete 2 contacts and queue 2 emails (not sent during the preview).')

@tagged('post_install', '-at_install')
class TestQueuedMailScope(TransactionCase):
    def test_hidden_recipients_not_shown(self):
        if 'mail.mail' not in self.env:
            self.skipTest('mail is not installed')
        user = self.env['res.users'].create({
            'name': 'PM plain', 'login': 'pm_plain', 'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        secret = self.env['res.partner'].create({'name': 'Secret', 'email': 'secret@example.com'})
        mail = self.env['mail.mail'].sudo().create({
            'subject': 'S', 'email_to': 'raw@example.com', 'recipient_ids': [(4, secret.id)]})
        rec = ChangeRecorder(user.id)
        rec.note_create(mail)
        # the user can read the partner but not the mail row: partner address shown, raw address hidden
        self.assertEqual(rec.emails[0]['to'], 'secret@example.com, 1 hidden')
        self.assertEqual(rec.emails[0]['subject'], 'S')


@tagged('post_install', '-at_install')
class TestSections(TransactionCase):
    """The extension point: a module overrides preview.mode.section._preview_sections."""

    def _preview(self, func):
        Section = type(self.env['preview.mode.section'])
        partner = self.env['res.partner'].create({'name': 'Section Co'})
        with patch.object(Section, '_preview_sections', func):
            return build_preview(self.env, 'res.partner', 'copy', [partner.id], [], {}, 'Copy')

    def test_section_is_returned_and_sees_the_changes(self):
        def sections(self, model, method, res_ids, changes):
            names = [c['what'] for c in changes if c['kind'] == 'new']
            return [{'title': 'Extra', 'columns': ['Name'], 'rows': [[n] for n in names]}]
        payload = self._preview(sections)
        self.assertEqual(len(payload['sections']), 1, payload)
        self.assertEqual(payload['sections'][0]['title'], 'Extra')
        self.assertEqual(len(payload['sections'][0]['rows']), 1)

    def test_default_has_no_sections(self):
        payload = build_preview(self.env, 'res.partner', 'copy', [self.env['res.partner'].create({'name': 'P'}).id],
                                [], {}, 'Copy')
        self.assertEqual(payload['sections'], [])

    def test_broken_section_does_not_break_the_preview(self):
        def sections(self, model, method, res_ids, changes):
            raise ValueError('boom')
        payload = self._preview(sections)
        self.assertEqual(payload['sections'], [])
        self.assertTrue(payload['changes'])
