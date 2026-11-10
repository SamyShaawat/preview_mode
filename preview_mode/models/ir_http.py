from odoo import models

from .payload import switched_on


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # session_info lives on ir.http (web) from 16 to 20; only the field read is ours.
    def session_info(self):
        info = super().session_info()
        available = switched_on(self.env)
        info['preview_mode_available'] = available
        info['preview_mode_enabled'] = available and self.env.user.preview_mode_enabled
        return info
