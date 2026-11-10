from odoo import api, models


class PreviewModeSection(models.AbstractModel):
    """Extension point: other modules add their own tables to the preview popup.

    Override `_preview_sections` with `_inherit = 'preview.mode.section'` (see the README).
    """
    _name = 'preview.mode.section'
    _description = 'Preview Mode Extra Sections'

    @api.model
    def _preview_sections(self, model, method, res_ids, changes):
        """Return extra tables for the popup: [{'title': str, 'columns': [str], 'rows': [[str]]}].

        Runs inside the preview, before the rollback, so the records the click created or changed
        can still be read. `changes` is the merged list the popup shows: dicts with kind
        ('new', 'changed', 'deleted'), model, res_id, what and fields. Always call super and
        append to its result. Read only: never write here.
        """
        return []
