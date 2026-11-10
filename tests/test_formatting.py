from types import SimpleNamespace

from odoo.tests.common import TransactionCase, tagged

from ..models.formatting import display_value
from ..models.payload import build_preview


@tagged('post_install', '-at_install')
class TestFormatting(TransactionCase):
    def test_monetary_shows_symbol_and_decimals(self):
        # base has no model with a monetary field, so a stand-in field drives display_value.
        currency = self.env.ref('base.USD')
        company = self.env.company
        company.currency_id = currency
        field = SimpleNamespace(type='monetary', get_currency_field=lambda record: 'currency_id')
        shown = display_value(company, field, 1234.5)
        self.assertIn(currency.symbol, shown)
        self.assertIn('1,234.50', shown)

    def test_boolean_shows_yes_or_no(self):
        partner = self.env['res.partner']
        active = partner._fields['active']
        self.assertEqual(display_value(partner, active, True), 'Yes')
        self.assertEqual(display_value(partner, active, False), 'No')
        self.assertEqual(display_value(partner, active, None), 'No')

    def test_archive_shows_yes_then_no(self):
        partner = self.env['res.partner'].create({'name': 'Bool Test'})
        out = build_preview(self.env, 'res.partner', 'action_archive', partner.ids, [], {}, 'Archive')
        fields = out['changes'][0]['fields']
        self.assertEqual([(f['old'], f['new']) for f in fields if f['label'] == 'Active'], [('Yes', 'No')])
