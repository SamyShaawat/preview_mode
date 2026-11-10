from odoo.http import Controller, request, route

from ..models.payload import build_preview
from ..models.recorder import _can_read
from ..models.where import locate

# PORT: the RPC route type is 'jsonrpc' on Odoo 19/20 and 'json' on 16 to 18.
RPC = 'json'


def _is_child_model(model):
    # A line-like model (a required parent that deletes it by cascade) is part of its parent's
    # link in the toast, e.g. journal items belong to the journal entry.
    return any(f.type == 'many2one' and f.required and f.ondelete == 'cascade' for f in model._fields.values())


class PreviewModeController(Controller):
    # Never readonly: the preview needs a savepoint on a writable cursor.

    @route('/preview_mode/run', type=RPC, auth='user')
    def preview_mode_run(self, model, method, res_ids, args=None, kwargs=None, label=''):
        # The request's own env and rights, never sudo.
        return build_preview(request.env, model, method, res_ids or [], args or [], kwargs or {}, label)

    @route('/preview_mode/created', type=RPC, auth='user')
    def preview_mode_created(self, token):
        rows = request.env['preview.mode.created'].search([
            ('token', '=', token), ('create_uid', '=', request.env.uid)])
        env = request.env
        # A deleted record (empty recordset) would pass the access check, so require it to exist.
        rows_shown = rows.browse()
        for row in rows:
            rec = env[row.model].browse(row.res_id).exists() if row.model in env else None
            if rec and not _is_child_model(rec) and _can_read(rec):
                rows_shown |= row
        result = [{
            'model': row.model,
            'res_id': row.res_id,
            'name': row.name,
            'menu_path': locate(request.env, row.model, row.res_id),
        } for row in rows_shown]
        rows.unlink()
        return result
