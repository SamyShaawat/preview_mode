from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # PORT: `user_writeable=True` is the Odoo 20 way; on 16 to 19 add the field to
    # SELF_WRITEABLE_FIELDS / SELF_READABLE_FIELDS instead.
    preview_mode_enabled = fields.Boolean(string='Preview Mode', default=False, user_writeable=True)
