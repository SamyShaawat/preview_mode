from types import SimpleNamespace

from odoo.tests.common import TransactionCase, tagged

from ..models.formatting import display_value


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
