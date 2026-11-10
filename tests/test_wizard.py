from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from ..models.payload import build_preview


@tagged('post_install', '-at_install')
class TestWizardButtons(TransactionCase):
    """Buttons of wizards (transient models) are previewed like any other button.

    The wizard row itself is never listed; what the button does to real records is."""

    def _preview(self, wizard, method, label):
        return build_preview(self.env, wizard._name, method, wizard.ids, [], {}, label)

    def test_wizard_button_changing_data_is_previewed(self):
        partner = self.env['res.partner'].create({'name': 'Wizard Co'})
        wizard = self.env['base.document.layout'].create({})
        Wizard = type(wizard)

        def confirm(self):
            partner.write({'ref': 'WIZ-1'})
        with patch.object(Wizard, 'preview_mode_test_confirm', confirm, create=True):
            payload = self._preview(wizard, 'preview_mode_test_confirm', 'Confirm')
        self.assertTrue(payload['show'], payload)
        self.assertEqual([r['what'] for r in payload['changes']], ['Wizard Co'])
        self.assertEqual(payload['changes'][0]['kind'], 'changed')
        self.assertFalse(partner.ref)  # rolled back
        self.assertTrue(wizard.exists())

    def test_wizard_close_button_is_not_previewed(self):
        wizard = self.env['base.document.layout'].create({})

        def close(self):
            return {'type': 'ir.actions.act_window_close'}
        with patch.object(type(wizard), 'preview_mode_test_close', close, create=True):
            payload = self._preview(wizard, 'preview_mode_test_close', 'Close')
        self.assertFalse(payload['show'])
        self.assertEqual(payload['changes'], [])

    def test_payment_register_wizard(self):
        if 'account.payment.register' not in self.env:
            self.skipTest('account is not installed')
        partner = self.env['res.partner'].create({'name': 'Customer Y'})
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': partner.id, 'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {'name': 'Item', 'quantity': 1, 'price_unit': 100})],
        })
        invoice.action_post()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({})
        payload = self._preview(wizard, 'action_create_payments', 'Create Payment')
        self.assertTrue(payload['show'], payload)
        self.assertTrue(any(r['kind'] == 'new' for r in payload['changes']), payload)
        self.assertTrue(all(r['where'] is not None for r in payload['changes']))
        self.assertEqual(invoice.payment_state, 'not_paid')
        self.assertFalse(self.env['account.payment'].search([('partner_id', '=', partner.id)]))

    def test_credit_note_wizard(self):
        if 'account.move.reversal' not in self.env:
            self.skipTest('account is not installed')
        partner = self.env['res.partner'].create({'name': 'Customer Z'})
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': partner.id, 'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {'name': 'Item', 'quantity': 1, 'price_unit': 50})],
        })
        invoice.action_post()
        wizard = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({'reason': 'Return', 'journal_id': invoice.journal_id.id})
        payload = self._preview(wizard, 'reverse_moves', 'Reverse')  # PORT: refund_moves on 17 and later
        self.assertTrue(payload['show'], payload)
        self.assertTrue(any(r['kind'] == 'new' and r['where'] for r in payload['changes']), payload)
        self.assertFalse(invoice.reversal_move_ids)
