from odoo import api, models

from .recorder import IGNORED_MODELS, active_recorder


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        recorder = active_recorder()
        if recorder is not None:
            recorder.note_create(records)
        token = self.env.context.get('preview_mode_token')
        if token and not self.env.su and not records._transient and records._name not in IGNORED_MODELS:
            # sudo creates are skipped: the user may not be allowed to see them.
            # Stored in the database, not memory: the toast request may hit another worker.
            self.env['preview.mode.created'].create([
                {'token': token, 'model': rec._name, 'res_id': rec.id, 'name': rec.display_name}
                for rec in records])
        return records

    def write(self, vals):
        recorder = active_recorder()
        if recorder is None:
            return super().write(vals)
        old = recorder.snapshot(self, vals)
        result = super().write(vals)
        recorder.note_write(self, old, vals)
        return result

    def unlink(self):
        recorder = active_recorder()
        if recorder is not None:
            recorder.note_unlink(self)
        return super().unlink()

    def _write(self, vals):
        # PORT: Odoo 16 has no _write_multi; delayed writes (recomputed stored fields, cascades) reach the
        # database through _write(vals). write() calls it too, so a record may be noted twice; the merge in
        # payload._merge keeps the first old value and the last new one. 18 to 20 hook _write_multi(vals_list).
        recorder = active_recorder()
        if recorder is None:
            return super()._write(vals)
        names, old = recorder.snapshot_columns(self, [vals])
        result = super()._write(vals)
        if names:
            recorder.note_write(self, old, dict.fromkeys(names))
        return result
