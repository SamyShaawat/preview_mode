from odoo.tests.common import HttpCase, tagged


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

    def test_run_route_returns_payload(self):
        partner = self.env['res.partner'].create({'name': 'Route Co'})
        self.authenticate('admin', 'admin')
        payload = self.make_jsonrpc_request('/preview_mode/run', {
            'model': 'res.partner', 'method': 'copy', 'res_ids': [partner.id],
            'args': [], 'kwargs': {}, 'label': 'Duplicate'})
        self.assertTrue(payload['changes'], payload)
        self.assertEqual(payload['changes'][0]['kind'], 'new')
        self.assertEqual(self.env['res.partner'].search_count([('name', 'like', 'Route Co')]), 1)
