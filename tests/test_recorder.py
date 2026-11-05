from unittest.mock import patch

from odoo.models import BaseModel
from odoo.tests.common import TransactionCase, tagged

from ..models.recorder import ChangeRecorder, active_recorder


@tagged('post_install', '-at_install')
class TestRecorder(TransactionCase):

    def test_create_is_recorded(self):
        with ChangeRecorder() as rec:
            self.env['res.partner'].create({'name': 'A'})
        self.assertEqual(len(rec.changes), 1)
        change = rec.changes[0]
        self.assertEqual(change.kind, 'new')
        self.assertEqual(change.model, 'res.partner')
        self.assertEqual(change.display_name, 'A')

    def test_write_records_old_and_new(self):
        partner = self.env['res.partner'].create({'name': 'A'})
        with ChangeRecorder() as rec:
            partner.write({'name': 'B'})
        # Two entries for one record: the write itself, and the recomputed stored field (complete_name)
        # seen at flush. The payload merges them into one row.
        self.assertEqual({(c.kind, c.res_id) for c in rec.changes}, {('changed', partner.id)})
        self.assertIn([('Name', 'A', 'B')], [c.fields for c in rec.changes])

    def test_unlink_is_recorded(self):
        partner = self.env['res.partner'].create({'name': 'A'})
        with ChangeRecorder() as rec:
            partner.unlink()
        self.assertEqual([c.kind for c in rec.changes], ['deleted'])

    def test_ignored_models_and_fields(self):
        partner = self.env['res.partner'].create({'name': 'A'})
        with ChangeRecorder() as rec:
            self.env['ir.attachment'].create({'name': 'f', 'raw': b'x'})
            partner.write({'write_date': '2020-01-01 00:00:00'})
        self.assertEqual(rec.changes, [])

    def test_transient_ignored(self):
        with ChangeRecorder() as rec:
            self.env['base.language.install'].create({})
        self.assertEqual(rec.changes, [])

    def test_no_recorder_means_no_effect(self):
        self.assertIsNone(active_recorder())
        partner = self.env['res.partner'].create({'name': 'A'})
        with patch.object(BaseModel, 'read', autospec=True) as read:
            partner.write({'name': 'B'})
        read.assert_not_called()
        self.assertEqual(partner.name, 'B')

    def test_recorder_cleared_after_exception(self):
        with self.assertRaises(ValueError):
            with ChangeRecorder():
                self.assertIsNotNone(active_recorder())
                raise ValueError
        self.assertIsNone(active_recorder())

    def test_ignored_model_write_does_not_read(self):
        att = self.env['ir.attachment'].create({'name': 'f', 'raw': b'x'})
        with ChangeRecorder() as rec:
            with patch.object(BaseModel, 'read', autospec=True) as read:
                att.write({'raw': b'y'})
        read.assert_not_called()
        self.assertEqual(rec.changes, [])

    def test_many2many_only_write(self):
        partner = self.env['res.partner'].create({'name': 'A'})
        cat = self.env['res.partner.category'].create({'name': 'Cat'})
        with ChangeRecorder() as rec:
            partner.write({'category_id': [(6, 0, cat.ids)]})
        self.assertEqual(rec.changes[0].fields, [('Tags', '', 'Cat')])

    def test_binary_only_write(self):
        partner = self.env['res.partner'].create({'name': 'A'})
        png = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/'
               'iZk9HQAAAABJRU5ErkJggg==')
        with ChangeRecorder() as rec:
            partner.write({'image_1920': png})
        self.assertEqual(rec.changes[0].fields, [('Image', '', '(changed)')])

    def test_snapshot_failure_does_not_break_write(self):
        partner = self.env['res.partner'].create({'name': 'A'})
        with ChangeRecorder() as rec:
            with patch.object(BaseModel, 'read', side_effect=RuntimeError):
                partner.write({'name': 'B'})
        self.assertEqual(partner.name, 'B')
        self.assertTrue(rec.incomplete)
        self.assertTrue(rec.warnings)


@tagged('post_install', '-at_install')
class TestDisplayValue(TransactionCase):
    def test_numbers_and_dates_are_formatted_for_the_user(self):
        from datetime import date, datetime
        from ..models.formatting import display_value
        partner = self.env['res.partner'].create({'name': 'Fmt Co'})
        latitude = partner._fields['partner_latitude']
        self.assertEqual(display_value(partner, latitude, 1234.5), '1,234.5000000')
        self.assertTrue(display_value(partner, partner._fields['create_date'], datetime(2026, 1, 31, 10, 0))
                        .startswith('01/31/2026'))
        cron = self.env['ir.cron'].search([], limit=1)
        self.assertTrue(display_value(cron, cron._fields['nextcall'], datetime(2026, 1, 31, 10, 0))
                        .startswith('01/31/2026'))
        rate = self.env['res.currency.rate']
        self.assertEqual(display_value(rate, rate._fields['name'], date(2026, 1, 31)), '01/31/2026')
        self.assertIsNone(display_value(partner, partner._fields['name'], 'x'))


@tagged('post_install', '-at_install')
class TestSnapshotColumns(TransactionCase):
    def test_empty_many2one_column_is_read_without_marking_incomplete(self):
        # Stock moves, pickings and most real records have empty many2one columns.
        partner = self.env['res.partner'].create({'name': 'No Parent Co'})
        recorder = ChangeRecorder()
        names, old = recorder.snapshot_columns(partner, [{'parent_id': False, 'name': 'x'}])
        self.assertIn('parent_id', names)
        self.assertEqual(old[partner.id]['parent_id'], '')
        self.assertEqual(old[partner.id]['name'], 'No Parent Co')
        self.assertFalse(recorder.incomplete, recorder.warnings)
