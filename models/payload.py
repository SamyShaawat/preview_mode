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
        if change['kind'] == 'new':
            created[change['model']] = created.get(change['model'], 0) + 1
    for model, count in created.items():
        parts.append(_('create %(count)s %(what)s', count=count, what=env[model]._description.lower()))
    updated = sum(1 for c in changes if c['kind'] == 'changed')
    deleted = sum(1 for c in changes if c['kind'] == 'deleted')
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


def _merge(changes):
    """One row per record: many writes to the same record become one row.

    A record created in the run stays 'new' (later writes are part of its creation);
    a field written twice keeps its first old value and last new value; unchanged fields drop out.
    """
    by_record = {}
    for c in changes:
        row = by_record.setdefault((c.model, c.res_id), {
            'kind': c.kind, 'model': c.model, 'res_id': c.res_id, 'what': c.display_name, 'fields': {}})
        if c.kind == 'deleted' or row['kind'] == 'changed':
            row['kind'] = c.kind
        if c.display_name and c.display_name.lower() != 'false':
            row['what'] = c.display_name
        for label, old, new in c.fields:
            first_old = row['fields'].get(label, (old, new))[0]
            row['fields'][label] = (first_old, new)
    for row in by_record.values():
        row['fields'] = {k: v for k, v in row['fields'].items() if v[0] != v[1]}
        if row['kind'] == 'new':
            row['fields'] = {}  # a new record is listed once, not field by field
    return [r for r in by_record.values() if r['kind'] != 'changed' or r['fields']]


def _journal(env, changes):
    """Debit/credit lines of the journal entries the click creates or posts (only with Accounting).

    Must run inside the savepoint, while the lines still exist.
    """
    if 'account.move' not in env:
        return []
    ids = {c.res_id for c in changes if c.model == 'account.move' and c.kind != 'deleted'}
    result = []
    for move in env['account.move'].browse(ids).exists():
        if move.state != 'posted' and not any(c.kind == 'new' and c.res_id == move.id for c in changes):
            continue
        lines = [{'account': line.account_id.display_name or '', 'debit': line.debit, 'credit': line.credit}
                 for line in move.line_ids if line.debit or line.credit]
        if lines:
            result.append({
                'move': move.name or move.display_name,
                'lines': lines,
                'balanced': round(sum(l['debit'] for l in lines) - sum(l['credit'] for l in lines), 6) == 0,
            })
    return result


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
            # Delayed writes (recomputed totals, states) only reach the recorder when flushed, and the
            # savepoint rollback drops them unflushed.
            env.flush_all()
        except UserError as e:  # also AccessError, ValidationError
            warnings.append({'text': _('Confirming will fail: %s', e.args[0] if e.args else e), 'blocking': True})
        except (PreviewBlocked, PreviewIncomplete):
            pass  # already recorded as incomplete by the guard
        try:
            journal = _journal(env, recorder.changes)
        except Exception:  # noqa: BLE001 - the extra view must never break the preview
            journal = []
    # The savepoint is rolled back here; Change rows already hold plain text.
    warnings += [{'text': text, 'blocking': False} for text in recorder.warnings]
    changes = recorder.changes
    where = {}
    rows = []
    merged = _merge(changes)
    for change in merged[:MAX_ROWS]:
        if change['model'] not in where:
            where[change['model']] = locate(env, change['model'])
        rows.append({
            'kind': change['kind'],
            # Records without a real name show as "model,id"; say what they are instead.
            'what': env[change['model']]._description if change['what'] == '%s,%s' % (change['model'], change['res_id']) else change['what'],
            'where': where[change['model']],
            'fields': [{'label': lbl, 'old': old, 'new': new} for lbl, (old, new) in change['fields'].items()],
        })
    if len(merged) > MAX_ROWS:
        rows.append({'kind': 'more', 'what': _('and %s more', len(merged) - MAX_ROWS), 'where': '', 'fields': []})
    blocking = [w for w in warnings if w['blocking']]
    summary = _summary(env, merged, recorder.emails)
    if blocking and not summary:
        summary = blocking[0]['text']
    return {
        # The client decides on `show`, never on `changes == []`.
        'show': bool(rows or blocking or recorder.incomplete or recorder.emails),
        'changes': rows,
        'emails': recorder.emails,
        'warnings': warnings,
        'incomplete': recorder.incomplete,
        'summary': summary,
        'journal': journal,
    }
