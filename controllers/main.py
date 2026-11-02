from odoo.exceptions import AccessError
from odoo.http import Controller, request, route

from ..models.payload import build_preview
from ..models.where import locate

# PORT: the RPC route type is 'jsonrpc' on Odoo 19/20 and 'json' on 16 to 18.
RPC = 'json'


def _readable(records):
    # PORT: has_access exists on Odoo 18+; 16 and 17 need the rights + rules pair.
    if hasattr(records, 'has_access'):
        return records.has_access('read')
    if not records.check_access_rights('read', raise_exception=False):
        return False
    try:
        records.check_access_rule('read')
    except AccessError:
        return False
    return True


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
        rows_shown = []
        for row in rows:
            if row.model not in env:
                continue
            rec = env[row.model].browse(row.res_id).exists()
            if rec and _readable(rec):
                rows_shown.append(row)
        result = [{
            'model': row.model,
            'res_id': row.res_id,
            'name': row.name,
            'menu_path': locate(request.env, row.model),
        } for row in rows_shown]
        rows.unlink()
        return result
