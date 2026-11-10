from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'preview_mode')
class TestPreviewTours(HttpCase):
    """Browser tours; need a headless Chrome (HttpCase skips cleanly without one)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.user_admin').preview_mode_enabled = False
        cls.partner = cls.env['res.partner'].create({'name': 'Tour Partner'})
        # Two test buttons on the partner form, so no extra app is needed:
        # `copy` creates a record, `open_commercial_entity` changes nothing.
        cls.env['ir.ui.view'].create({
            'name': 'preview_mode.test.partner.buttons',
            'model': 'res.partner',
            'inherit_id': cls.env.ref('base.view_partner_form').id,
            'arch': '''<xpath expr="//sheet" position="before">
                <header>
                    <button name="copy" type="object" string="Duplicate Contact"/>
                    <button name="open_commercial_entity" type="object" string="Open Entity"/>
                </header></xpath>''',
        })

    def _tour(self, name):
        url = '/odoo/action-base.action_partner_form/%d' % self.partner.id
        self.start_tour(url, name, login='admin')

    def test_toggle(self):
        self._tour('preview_mode_toggle')

    def test_popup_confirm_creates_record_with_toast(self):
        self._tour('preview_mode_confirm')
        self.assertEqual(self.env['res.partner'].search_count([('name', '=', 'Tour Partner (copy)')]), 1)

    def test_kill_switch_removes_the_toggle(self):
        self.env['ir.config_parameter'].set_bool('preview_mode.enabled', False)
        self._tour('preview_mode_switched_off')
        self.assertEqual(self.env['res.partner'].search_count([('name', '=', 'Tour Partner (copy)')]), 1)

    def test_no_change_click_has_no_popup(self):
        self._tour('preview_mode_no_popup')
