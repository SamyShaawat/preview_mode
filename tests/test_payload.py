from email.message import EmailMessage
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from ..models.payload import build_preview


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
        self.assertTrue(payload['summary'])

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

    def test_payload_failing_button_is_blocking_warning(self):
        def button(self):
            raise UserError('Period locked')
        with self._patch(button):
            payload = build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, 'Post')
        self.assertIn({'text': 'Confirming will fail: Period locked', 'blocking': True}, payload['warnings'])

    def test_registry_changing_models_are_never_run(self):
        for model in ('ir.module.module', 'res.config.settings', 'base.module.upgrade', 'ir.ui.view'):
            with patch('odoo.addons.preview_mode.models.payload.call_kw') as call_kw:
                payload = build_preview(self.env, model, 'execute', [1], [], {}, 'Go')
            call_kw.assert_not_called()
            self.assertFalse(payload['show'], model)

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
        with self.assertRaises(Exception):
            build_preview(self.env, 'res.partner', '_compute_display_name', [self.partner.id], [], {}, 'x')

    def test_user_flag_is_self_writable(self):
        user = new_test_user(self.env, 'preview_flag', groups='base.group_user')
        user.with_user(user).write({'preview_mode_enabled': True})
        self.assertTrue(user.preview_mode_enabled)


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
        self.assertEqual(sum(l['debit'] for l in result['journal'][0]['lines']),
                         sum(l['credit'] for l in result['journal'][0]['lines']))
        self.assertEqual(bill.state, 'draft')
