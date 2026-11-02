from odoo.http import Controller, request, route

from ..models.payload import build_preview
from ..models.where import locate

# PORT: the RPC route type is 'jsonrpc' on Odoo 19/20 and 'json' on 16 to 18.
RPC = 'jsonrpc'


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
        result = [{
            'model': row.model,
            'res_id': row.res_id,
            'name': row.name,
            'menu_path': locate(request.env, row.model),
        } for row in rows]
        rows.unlink()
        return result
