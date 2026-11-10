from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # PORT: Odoo 20 uses `user_writeable=True`; on 16 to 19 the field is listed in SELF_WRITEABLE_FIELDS
    # and SELF_READABLE_FIELDS below.
    preview_mode_enabled = fields.Boolean(string='Preview Mode', default=False)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['preview_mode_enabled']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['preview_mode_enabled']
