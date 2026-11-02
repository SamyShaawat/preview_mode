from odoo import api, models

from .recorder import active_recorder


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        recorder = active_recorder()
        if recorder is not None:
            recorder.note_create(records)
        return records

    def write(self, vals):
        recorder = active_recorder()
        if recorder is None:
            return super().write(vals)
        old = self.read([n for n in vals if n in self._fields])
        result = super().write(vals)
        recorder.note_write(self, old, vals)
        return result

    def unlink(self):
        recorder = active_recorder()
        if recorder is not None:
            recorder.note_unlink(self)
        return super().unlink()
