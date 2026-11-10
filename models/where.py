"""Where would the user find a record: the menu path of its model."""
from lxml import etree

from odoo import fields, tools
from odoo.tools.safe_eval import safe_eval

SEPARATOR = ' › '
PARENT_FIELDS = ('move_id', 'order_id', 'picking_id')
NOT_A_PARENT = ('company_id', 'currency_id')


def _eval(env, text, default):
    try:
        return safe_eval(text, {'uid': env.uid, 'user': env.user, 'context_today': fields.Date.context_today,
                                'time': tools.safe_eval.time, 'datetime': tools.safe_eval.datetime,
                                'dateutil': tools.safe_eval.dateutil,
                                'context': env.context}) if text else default
    except Exception:  # noqa: BLE001 - an odd domain only means "no opinion", never an error
        return default


def _filter_domains(env, action):
    """Domains of the search filters the action switches on by default (``search_default_*`` in its context)."""
    names = [k[len('search_default_'):] for k, v in (_eval(env, action.context, {}) or {}).items()
             if k.startswith('search_default_') and v]
    if not names:
        return []
    try:
        arch = env[action.res_model].get_view(action.search_view_id.id or None, 'search')['arch']
        root = etree.fromstring(arch.encode())
    except Exception:  # noqa: BLE001
        return []
    domains = []
    for name in names:
        for node in root.iterfind('.//filter[@name="%s"]' % name):
            domain = _eval(env, node.get('domain'), None)
            if domain:
                domains.append(domain)
    return domains


def candidates(env, model_name):
    """Visible menus whose window action opens ``model_name`` (path, action domain, default filters)."""
    Menu = env['ir.ui.menu']
    visible = Menu._visible_menu_ids()
    actions = env['ir.actions.act_window'].sudo().search([('res_model', '=', model_name)])
    if not actions:
        return []
    owners = (env['ir.model'].sudo()._get(model_name).modules or '').replace(' ', '').split(',')
    result = []
    for menu in Menu.sudo().search([
            ('id', 'in', list(visible)),
            ('action', 'in', ['ir.actions.act_window,%d' % a.id for a in actions])]):
        action, chain, node = menu.action, [], menu
        while node:
            if node.id not in visible:  # a hidden ancestor makes the menu unreachable
                break
            chain.insert(0, node.name)
            node = node.parent_id
        else:
            xmlid = action.get_external_id().get(action.id) or ''
            result.append({
                'path': SEPARATOR.join(chain),
                'domain': _eval(env, action.domain, []),
                'filters': _filter_domains(env, action),
                # Best first: the app that owns the model, then shortest path, then menu order.
                'rank': (xmlid.split('.')[0] not in owners, len(chain), menu.sequence, menu.id),
            })
    return result


def _fits(record, domain):
    try:
        return bool(record.filtered_domain(domain)) if domain else True
    except Exception:  # noqa: BLE001
        return True


def _hits(record, cand):
    """How many default filters of the menu fit the record AND test a selection field (state, type...)."""
    fields_ = record._fields
    return sum(
        1 for domain in cand['filters'] if _fits(record, domain) and any(
            isinstance(leaf, (tuple, list)) and len(leaf) == 3 and leaf[0] in fields_
            and fields_[leaf[0]].type == 'selection' for leaf in domain))


def _menu_path(env, model_name, res_id=None, cands=None, values=None):
    """Path of the menu that really shows this kind of record, or None.

    With a live record (or the values it had before it was deleted), a menu whose action domain excludes it
    is dropped. Then the app that owns the
    model wins, then the menu whose default filter picks the record's state or type (Orders over
    Quotations for a confirmed order), then the shortest path, then menu order.
    """
    cands = candidates(env, model_name) if cands is None else cands
    record = res_id and env[model_name].sudo().browse(res_id).exists()
    if not record and values:  # deleted in the preview: a virtual record with its old values
        record = env[model_name].sudo().new(values)
    if record:
        cands = [c for c in cands if _fits(record, c['domain'])]
    cands = sorted(cands, key=lambda c: (c['rank'][0], -(_hits(record, c) if record else 0), c['rank']))
    return cands[0]['path'] if cands else None


def _parent_field(model):
    """First required many2one that is the record's parent (not a delegation), or None.

    A parent is a record the child cannot outlive (``ondelete='cascade'``): an invoice line has one, a sales
    order does not (its customer is no place to look for it).
    """
    fields = [f for f in model._fields.values()
              if f.type == 'many2one' and f.required and f.name not in NOT_A_PARENT
              and f.name not in model._inherits.values() and (f.ondelete == 'cascade' or f.name in PARENT_FIELDS)]
    fields.sort(key=lambda f: f.name not in PARENT_FIELDS)
    return fields[0] if fields else None


def locate(env, model_name, res_id=None, cands=None, values=None):
    """Menu path for a record of ``model_name``; ``values`` are those of a record deleted in the preview.

    Call inside the preview savepoint, while a live record still exists.
    """
    model = env[model_name]
    path = _menu_path(env, model_name, res_id, cands, values)
    if path is None:
        field = _parent_field(model)
        if field:
            record = res_id and model.sudo().browse(res_id).exists()
            parent = record and record[field.name].id or values and values.get(field.name) or None
            path = _menu_path(env, field.comodel_name, parent)
    return path or model._description
