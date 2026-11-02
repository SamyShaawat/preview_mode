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
        partner.write({'name': 'B'})
        self.assertEqual(partner.name, 'B')

    def test_recorder_cleared_after_exception(self):
        with self.assertRaises(ValueError):
            with ChangeRecorder():
                self.assertIsNotNone(active_recorder())
                raise ValueError
        self.assertIsNone(active_recorder())
