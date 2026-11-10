import threading
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from ..models.payload import build_preview
from ..models.rawwrites import _cascaded


@tagged('post_install', '-at_install')
class TestRawWrites(TransactionCase):
    """A click that writes with raw SQL must make the preview incomplete; ORM-only clicks must not."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Raw Co'})
        cls.Partner = type(cls.env['res.partner'])

    def _preview(self, button, label='Go'):
        with patch.object(self.Partner, 'preview_mode_test_button', button, create=True):
            return build_preview(self.env, 'res.partner', 'preview_mode_test_button', [self.partner.id], [], {}, label)

    def _warning(self, payload):
        return ' '.join(w['text'] for w in payload['warnings'])

    def test_raw_update_is_flagged(self):
        def button(self):
            self.env.cr.execute("UPDATE res_country SET phone_code = 1 WHERE id = (SELECT min(id) FROM res_country)")
        payload = self._preview(button)
        self.assertTrue(payload['incomplete'])
        self.assertIn('res_country', self._warning(payload))
        self.assertTrue(payload['show'])

    def test_raw_partner_update_is_tolerated(self):
        # PORT: Odoo 16 to 18 Accounting bumps the partner rank with a raw UPDATE (see RAW_UPDATE_OK).
        def button(self):
            self.env.cr.execute("UPDATE res_partner SET comment = 'raw' WHERE id = %s", [self.id])
        self.assertFalse(self._preview(button)['incomplete'])

    def test_raw_insert_into_unrelated_table_is_flagged(self):
        def button(self):
            self.env.cr.execute(
                "INSERT INTO ir_config_parameter (key, value) VALUES ('preview_mode.raw_test', '1')")
        payload = self._preview(button)
        self.assertTrue(payload['incomplete'])
        self.assertIn('ir_config_parameter', self._warning(payload))

    def test_raw_insert_next_to_an_orm_create_is_flagged(self):
        def button(self):
            self.env['ir.config_parameter'].create({'key': 'preview_mode.orm_made', 'value': '1'})
            self.env.cr.execute("INSERT INTO ir_config_parameter (key, value) VALUES ('preview_mode.raw_made', '1')")
        payload = self._preview(button)
        self.assertTrue(payload['incomplete'])
        self.assertIn('ir_config_parameter', self._warning(payload))

    def test_raw_delete_is_flagged(self):
        def button(self):
            self.env.cr.execute("DELETE FROM res_partner WHERE id = %s", [self.id])
        payload = self._preview(button)
        self.assertTrue(payload['incomplete'])

    def test_orm_only_clicks_are_complete(self):
        def write(self):
            self.write({'comment': 'orm'})

        def create_and_unlink(self):
            self.create({'name': 'Temp'}).unlink()
        for button in (write, create_and_unlink):
            payload = self._preview(button)
            self.assertFalse(payload['incomplete'], payload['warnings'])

    def test_select_and_no_op_are_complete(self):
        def button(self):
            self.env.cr.execute("SELECT count(*) FROM res_partner")
        self.assertFalse(self._preview(button)['incomplete'])

    def test_cascade_delete_is_not_a_raw_write(self):
        # Deleting a partner removes its bank accounts through a database foreign key cascade.
        self.env['res.partner.bank'].create({'partner_id': self.partner.id, 'acc_number': 'RAW-1'})  # PORT: account_number on 18+

        def button(self):
            self.unlink()
        payload = self._preview(button)
        self.assertFalse(payload['incomplete'], payload['warnings'])
        self.assertTrue(self.partner.exists())

    def test_cascade_deleted_lines_take_their_link_rows_along(self):
        """Unlinking an order deletes its lines by cascade; the lines' many2many tax link rows are not raw writes."""
        env = self.env
        if 'sale.order' not in env or 'account.tax' not in env:
            self.skipTest('needs sale and account')
        tax = env['account.tax'].create({'name': 'Raw Tax', 'amount': 5, 'type_tax_use': 'sale'})
        product = env['product.product'].create({'name': 'Raw Line Product'})
        order = env['sale.order'].create({
            'partner_id': self.partner.id,
            # PORT: 17 requires a product on a sale line (check constraint)
            'order_line': [(0, 0, {'product_id': product.id, 'name': 'Line', 'product_uom_qty': 1, 'price_unit': 10, 'tax_id': [(6, 0, tax.ids)]})]})  # PORT: tax_ids on 18+
        with patch.object(type(order), 'preview_mode_test_button', lambda self: self.unlink(), create=True):
            payload = build_preview(env, 'sale.order', 'preview_mode_test_button', order.ids, [], {}, 'Go')
        self.assertFalse(payload['incomplete'], payload['warnings'])

    def test_core_flows_are_complete(self):
        """Vendor bill post, sale confirm and picking validate: no false alarm (needs those apps)."""
        env = self.env
        missing = [m for m in ('account.move', 'sale.order', 'stock.picking') if m not in env]
        if missing or not env['account.journal'].search_count([('type', '=', 'purchase')]):
            self.skipTest('needs account (with a chart of accounts), sale and stock')
        product = env['product.product'].create({
            'name': 'Raw Test Product', 'detailed_type': 'product',
            'list_price': 10})  # PORT: type consu + is_storable on 18+
        bill = env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.partner.id, 'invoice_date': '2026-11-05',
            'invoice_line_ids': [(0, 0, {'name': 'Item', 'quantity': 2, 'price_unit': 100})]})
        order = env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 4})]})
        warehouse = env['stock.warehouse'].search([], limit=1)
        supplier = env.ref('stock.stock_location_suppliers')
        picking = env['stock.picking'].create({
            'partner_id': self.partner.id, 'picking_type_id': warehouse.in_type_id.id,
            'location_id': supplier.id, 'location_dest_id': warehouse.lot_stock_id.id,
            'move_ids': [(0, 0, {
                'name': 'Item',  # PORT: stock.move.name is required on 16 and 17
                'product_id': product.id, 'product_uom_qty': 5,
                'location_id': supplier.id, 'location_dest_id': warehouse.lot_stock_id.id})]})
        picking.action_confirm()
        picking.move_ids.quantity = 5
        for model, method, record in (
                ('account.move', 'action_post', bill),
                ('sale.order', 'action_confirm', order),
                ('stock.picking', 'button_validate', picking)):
            payload = build_preview(env, model, method, record.ids, [], {}, method)
            self.assertFalse(payload['incomplete'], (method, payload['warnings']))

    def test_mutual_cascade_terminates(self):
        """Two models that cascade into each other must not loop forever."""
        def field(comodel):
            return SimpleNamespace(type='many2one', store=True, comodel_name=comodel, ondelete='cascade')
        models = {n: SimpleNamespace(_auto=True, _abstract=False, _table=n, _fields={'x': field(o)})
                  for n, o in (('a', 'b'), ('b', 'a'))}
        env = type('Env', (), {'registry': list(models), '__getitem__': lambda self, n: models[n]})()
        out = []
        thread = threading.Thread(target=lambda: out.append(_cascaded(env, {'a'})), daemon=True)
        thread.start()
        thread.join(5)
        self.assertFalse(thread.is_alive(), '_cascaded does not terminate on mutual cascades')
        self.assertEqual(out[0][0], {'a', 'b'})
