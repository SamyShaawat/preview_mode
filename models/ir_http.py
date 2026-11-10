from odoo import models

from .payload import switched_on


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # session_info lives on ir.http (web) from 16 to 20; only the field read is ours.
    def session_info(self):
        info = super().session_info()
        info['preview_mode_enabled'] = self.env.user.preview_mode_enabled and switched_on(self.env)
        return info
