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
        self.assertEqual(len(rec.changes), 1)
        self.assertEqual(rec.changes[0].kind, 'changed')
        self.assertEqual(rec.changes[0].fields, [('Name', 'A', 'B')])

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
