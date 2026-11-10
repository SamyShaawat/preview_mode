from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    preview_mode_enabled = fields.Boolean(string='Preview Mode', default=False)

    # PORT: Odoo 16 to 19 list the self-editable fields in these properties
    # (Odoo 20 uses `user_writeable=True` on the field instead).
    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['preview_mode_enabled']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['preview_mode_enabled']
