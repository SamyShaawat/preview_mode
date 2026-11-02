from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestController(HttpCase):

    def test_created_endpoint_returns_and_clears(self):
        admin = self.env.ref('base.user_admin')
        self.env['res.partner'].with_user(admin).with_context(preview_mode_token='t1').create({'name': 'Real run'})
        self.authenticate('admin', 'admin')
        first = self.make_jsonrpc_request('/preview_mode/created', {'token': 't1'})
        self.assertEqual(len(first), 1, first)
        self.assertEqual(first[0]['model'], 'res.partner')
        self.assertEqual(first[0]['name'], 'Real run')
        self.assertEqual(self.make_jsonrpc_request('/preview_mode/created', {'token': 't1'}), [])

    def test_created_endpoint_skips_child_lines(self):
        admin = self.env.ref('base.user_admin')
        partner = self.env['res.partner'].with_user(admin).with_context(preview_mode_token='t9').create({'name': 'P'})
        self.env['res.partner.bank'].with_user(admin).with_context(preview_mode_token='t9').create({
            'partner_id': partner.id, 'account_number': '123456'})
        self.authenticate('admin', 'admin')
        models = [r['model'] for r in self.make_jsonrpc_request('/preview_mode/created', {'token': 't9'})]
        self.assertEqual(models, ['res.partner'])

    def test_run_route_returns_payload(self):
        partner = self.env['res.partner'].create({'name': 'Route Co'})
        self.authenticate('admin', 'admin')
        payload = self.make_jsonrpc_request('/preview_mode/run', {
            'model': 'res.partner', 'method': 'copy', 'res_ids': [partner.id],
            'args': [], 'kwargs': {}, 'label': 'Duplicate'})
        self.assertTrue(payload['changes'], payload)
        self.assertEqual(payload['changes'][0]['kind'], 'new')
        self.assertEqual(self.env['res.partner'].search_count([('name', 'like', 'Route Co')]), 1)

    def test_sudo_create_not_recorded(self):
        admin = self.env.ref('base.user_admin')
        self.env['res.partner'].with_user(admin).with_context(preview_mode_token='t2').sudo().create({'name': 'Hidden'})
        self.assertFalse(self.env['preview.mode.created'].search([('token', '=', 't2')]))

    def test_unreadable_record_not_returned(self):
        user = new_test_user(self.env, 'preview_reader', password='preview_reader', groups='base.group_user')
        param = self.env['ir.config_parameter'].create({'key': 'preview_mode.secret', 'value': 'x'})
        Created = self.env['preview.mode.created'].with_user(user)
        Created.create({'token': 't3', 'model': 'ir.config_parameter', 'res_id': param.id, 'name': 'secret'})
        Created.create({'token': 't3', 'model': 'res.partner', 'res_id': user.partner_id.id, 'name': 'Mine'})
        self.authenticate('preview_reader', 'preview_reader')
        result = self.make_jsonrpc_request('/preview_mode/created', {'token': 't3'})
        self.assertEqual([r['name'] for r in result], ['Mine'])
        self.assertFalse(self.env['preview.mode.created'].search([('token', '=', 't3')]))

    def _two_users_with_rows(self, token):
        user_a = new_test_user(self.env, 'preview_iso_a', password='preview_iso_a', groups='base.group_user')
        user_b = new_test_user(self.env, 'preview_iso_b', password='preview_iso_b', groups='base.group_user')
        self.env['preview.mode.created'].with_user(user_a).create({
            'token': token, 'model': 'res.partner', 'res_id': user_a.partner_id.id, 'name': 'A made'})
        # sudo only in the test, to see the rows regardless of ACL.
        rows_a = self.env['preview.mode.created'].sudo().search([('token', '=', token)])
        self.assertEqual(len(rows_a), 1)
        return user_a, user_b, rows_a

    def test_other_user_gets_nothing_and_deletes_nothing(self):
        user_a, user_b, rows_a = self._two_users_with_rows('iso1')
        self.authenticate('preview_iso_b', 'preview_iso_b')
        self.assertEqual(self.make_jsonrpc_request('/preview_mode/created', {'token': 'iso1'}), [])
        self.assertEqual(len(rows_a.exists()), 1)

    def test_other_user_cannot_read_rows_via_orm(self):
        user_a, user_b, rows_a = self._two_users_with_rows('iso2')
        Created = self.env['preview.mode.created'].with_user(user_b)
        self.assertFalse(Created.search([('token', '=', 'iso2')]))
        with self.assertRaises(AccessError):
            Created.browse(rows_a.ids).read(['name'])
        with self.assertRaises(AccessError):
            Created.browse(rows_a.ids).unlink()
        with self.assertRaises(AccessError):
            Created.browse(rows_a.ids).write({'name': 'hijacked'})
        self.assertEqual(rows_a.name, 'A made')

    def test_owner_gets_own_records_and_rows_removed(self):
        user_a, user_b, rows_a = self._two_users_with_rows('iso3')
        self.authenticate('preview_iso_a', 'preview_iso_a')
        result = self.make_jsonrpc_request('/preview_mode/created', {'token': 'iso3'})
        self.assertEqual([r['name'] for r in result], ['A made'])
        self.assertFalse(rows_a.exists())
