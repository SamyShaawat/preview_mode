"""Where would the user find a record: the menu path of its model."""

SEPARATOR = ' › '
PARENT_FIELDS = ('move_id', 'order_id', 'picking_id')
NOT_A_PARENT = ('company_id', 'currency_id')


def _menu_path(env, model_name):
    """Path of the nearest-to-root menu the user can open whose window action shows ``model_name``."""
    Menu = env['ir.ui.menu']
    visible = Menu._visible_menu_ids()
    actions = env['ir.actions.act_window'].sudo().search([('res_model', '=', model_name)])
    if not actions:
        return None
    menus = Menu.sudo().search([
        ('id', 'in', list(visible)),
        ('action', 'in', ['ir.actions.act_window,%d' % a.id for a in actions]),
    ])
    paths = []
    for menu in menus:
        chain = []
        while menu:
            if menu.id not in visible:  # a hidden ancestor makes the menu unreachable
                break
            chain.insert(0, menu.name)
            menu = menu.parent_id
        else:
            paths.append(chain)
    if not paths:
        return None
    return SEPARATOR.join(min(paths, key=len))


def _parent_model(model):
    """Comodel of the first required many2one that is the record's parent (not a delegation)."""
    fields = [f for f in model._fields.values()
              if f.type == 'many2one' and f.required and f.name not in NOT_A_PARENT
              and f.name not in model._inherits.values()]
    fields.sort(key=lambda f: f.name not in PARENT_FIELDS)
    return fields[0].comodel_name if fields else None


def locate(env, model_name, record=None):
    # ponytail: ``record`` is accepted for callers; the path only depends on the model today.
    model = env[model_name]
    path = _menu_path(env, model_name)
    if path is None:
        parent = _parent_model(model)
        path = parent and _menu_path(env, parent)
    return path or model._description
