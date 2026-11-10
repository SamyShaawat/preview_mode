from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    preview_mode_enabled = fields.Boolean(string='Preview Mode', default=False)

    # PORT: `user_writeable=True` is the Odoo 20 way; on 16 to 19 the field joins these two lists.
    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['preview_mode_enabled']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['preview_mode_enabled']
