"""Run a button inside safe_run and describe what it would do."""
from odoo import _
from odoo.exceptions import AccessError, UserError

try:  # PORT: Odoo 17 to 20
    from odoo.service.model import call_kw
except ImportError:  # Odoo 16
    from odoo.api import call_kw

from .guards import PreviewBlocked, PreviewIncomplete, safe_run
from .where import locate

MAX_ROWS = 200


def _summary(env, changes, emails):
    cr, uid, context = env.cr, env.uid, env.context  # noqa: F841 - read by _() to pick the language
    parts = []
    created = {}
    for change in changes:
        if change.kind == 'new':
            created[change.model] = created.get(change.model, 0) + 1
    for model, count in created.items():
        parts.append(_('create %(count)s %(what)s', count=count, what=env[model]._description.lower()))
    updated = sum(1 for c in changes if c.kind == 'changed')
    deleted = sum(1 for c in changes if c.kind == 'deleted')
    # ponytail: "record(s)" not real pluralisation; translators can phrase it per language.
    if updated:
        parts.append(_('update %s record(s)', updated))
    if deleted:
        parts.append(_('delete %s record(s)', deleted))
    if emails:
        parts.append(_('queue %s email(s) (not sent during the preview)', len(emails)))
    if not parts:
        return ''
    listed = parts[0] if len(parts) == 1 else _('%(first)s, and %(last)s', first=', '.join(parts[:-1]), last=parts[-1])
    return _('Confirming will %s.', listed)


def build_preview(env, model, method, res_ids, args, kwargs, label):
    """Same contract as call_button (args after the ids); no allow-list: any model, any method."""
    cr, uid, context = env.cr, env.uid, env.context  # noqa: F841 - read by _() to pick the language
    if method.startswith('_') or method == 'init':
        # Same rule as RPC: never run a private method (call_kw adds @api.private on 20).
        raise AccessError(_('Private methods cannot be previewed.'))
    warnings = []
    with safe_run(env) as recorder:
        try:
            # call_kw refuses private methods exactly like a real RPC would.
            call_kw(env[model], method, [list(res_ids), *args], kwargs)
        except UserError as e:  # also AccessError, ValidationError
            warnings.append({'text': _('Confirming will fail: %s', e.args[0] if e.args else e), 'blocking': True})
        except (PreviewBlocked, PreviewIncomplete):
            pass  # already recorded as incomplete by the guard
    # The savepoint is rolled back here; Change rows already hold plain text.
    warnings += [{'text': text, 'blocking': False} for text in recorder.warnings]
    changes = recorder.changes
    where = {}
    rows = []
    for change in changes[:MAX_ROWS]:
        if change.model not in where:
            where[change.model] = locate(env, change.model)
        rows.append({
            'kind': change.kind,
            'what': change.display_name,
            'where': where[change.model],
            'fields': [{'label': lbl, 'old': old, 'new': new} for lbl, old, new in change.fields],
        })
    if len(changes) > MAX_ROWS:
        rows.append({'kind': 'more', 'what': _('and %s more', len(changes) - MAX_ROWS), 'where': '', 'fields': []})
    return {
        'changes': rows,
        'emails': recorder.emails,
        'warnings': warnings,
        'incomplete': recorder.incomplete,
        'summary': _summary(env, changes, recorder.emails),
        'journal': [],
    }
