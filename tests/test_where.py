from odoo.tests.common import TransactionCase, new_test_user, tagged

from ..models.where import locate


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
