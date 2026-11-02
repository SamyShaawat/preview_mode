from odoo import fields, models


class PreviewModeCreated(models.TransientModel):
    """Records created by a real click that followed a preview, for the toast links."""
    _name = 'preview.mode.created'
    _description = 'Preview Mode Created Record'

    token = fields.Char(required=True, index=True)
    model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    name = fields.Char()
