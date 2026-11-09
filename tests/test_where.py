from odoo.tests.common import TransactionCase, new_test_user, tagged

from ..models.where import candidates, locate


@tagged('post_install', '-at_install')
class TestWhere(TransactionCase):
    # res.partner has no menu with only base/web installed (it comes with
    # contacts), so the menu tests use res.users (Settings › Users & Companies › Users).

    def test_where_uses_menu_path(self):
        path = locate(self.env, 'res.users')
        self.assertIn('›', path)
        self.assertTrue(path.endswith('Users'), path)

    def test_where_hides_inaccessible_menu(self):
        user = new_test_user(self.env, 'preview_where', groups='base.group_user')
        path = locate(self.env(user=user), 'res.users')
        self.assertEqual(path, self.env['res.users']._description)

    def test_where_falls_back_to_parent(self):
        self.assertEqual(locate(self.env, 'res.users.apikeys'), locate(self.env, 'res.users'))

    def test_where_picks_menu_whose_action_fits_the_record(self):
        root = self.env['ir.ui.menu'].create({'name': 'PM root'})
        for name, domain in (('Companies', "[('ref', '!=', False)]"), ('People', "[('ref', '=', False)]")):
            action = self.env['ir.actions.act_window'].create({'name': name, 'res_model': 'res.partner', 'domain': domain})
            self.env['ir.ui.menu'].create({'name': name, 'parent_id': root.id, 'action': '%s,%d' % (action._name, action.id)})
        company = self.env['res.partner'].create({'name': 'PM Co', 'ref': 'X'})
        person = self.env['res.partner'].create({'name': 'PM Joe'})
        # only the test menus, so installed apps do not change the answer
        cands = [c for c in candidates(self.env, 'res.partner') if c['path'].startswith('PM root')]
        self.assertEqual(locate(self.env, 'res.partner', company.id, cands), 'PM root › Companies')
        self.assertEqual(locate(self.env, 'res.partner', person.id, cands), 'PM root › People')

    def test_where_prefers_menu_whose_filter_picks_the_state(self):
        # The second menu's default filter tests a selection field the record matches, so it beats the first.
        root = self.env['ir.ui.menu'].create({'name': 'PM state root'})
        view = self.env['ir.ui.view'].create({
            'name': 'pm.users.search', 'model': 'res.users', 'type': 'search',
            'arch': '<search><filter name="pm_a" domain="[(\'notification_type\', \'=\', \'%s\')]"/></search>' % self.env.user.notification_type})
        for name, ctx in (('Plain', '{}'), ('Internal', "{'search_default_pm_a': 1}")):
            action = self.env['ir.actions.act_window'].create({
                'name': name, 'res_model': 'res.users', 'context': ctx, 'search_view_id': view.id})
            self.env['ir.ui.menu'].create({'name': name, 'parent_id': root.id, 'action': '%s,%d' % (action._name, action.id)})
        cands = [c for c in candidates(self.env, 'res.users') if c['path'].startswith('PM state root')]
        self.assertEqual(len(cands[1]['filters']), 1)
        self.assertEqual(locate(self.env, 'res.users', self.env.uid, cands), 'PM state root › Internal')
