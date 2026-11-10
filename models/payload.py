"""Run a button inside safe_run and describe what it would do."""
import re

from odoo import _
from odoo.exceptions import AccessError, UserError

try:  # PORT: Odoo 17 to 20
    from odoo.service.model import call_kw
except ImportError:  # Odoo 16
    from odoo.api import call_kw

from .compat import param_bool, param_float, param_int
from .guards import PreviewBlocked, PreviewIncomplete, safe_run
from .rawwrites import snapshot, unexplained
from .where import candidates, locate

MAX_ROWS = 200
# System parameters (all optional): preview_mode.enabled (kill switch, default on),
# preview_mode.timeout (seconds, default 10), preview_mode.max_records (0 = no limit).
DEFAULT_TIMEOUT = 10
MIN_TIMEOUT, MAX_TIMEOUT = 1, 120  # the parameter is clamped to this range (seconds)
# Buttons on these models change the in-memory registry, caches or installed modules, which a
# savepoint rollback cannot undo. They are never run as a preview: the real click runs as usual.
UNSAFE_MODELS = ('ir.module.module', 'res.config.settings', 'ir.model', 'ir.model.fields', 'ir.ui.view')
UNSAFE_PREFIXES = ('base.module.', 'base.language.')


def _timeout(env):
    seconds = param_float(env, 'preview_mode.timeout') or DEFAULT_TIMEOUT
    return max(MIN_TIMEOUT, min(MAX_TIMEOUT, seconds))


def _noun(env, model, count):
    """Model description in lower case, plural when ``count`` > 1 (English only, other languages keep the label)."""
    word = re.sub(r'\s*\(.*\)$', '', env[model]._description.lower())  # 'Product Moves (Stock Move Line)'
    if count == 1 or not (env.lang or 'en_US').startswith('en') or word.endswith('s'):
        return word
    # ponytail: plain English rules; add a per-model override if a description ever pluralises badly.
    if word.endswith('y') and word[-2:-1] not in 'aeiou':
        return word[:-1] + 'ies'
    return word + ('es' if word.endswith(('x', 'ch', 'sh')) else 's')


def _summary(env, changes, emails):
    cr, uid, context = env.cr, env.uid, env.context  # noqa: F841 - read by _() to pick the language
    parts = []
    for kind, text in (('new', _('create %(count)s %(what)s')),
                       ('changed', _('update %(count)s %(what)s')),
                       ('deleted', _('delete %(count)s %(what)s'))):
        counts = {}
        for change in changes:
            if change['kind'] == kind:
                counts[change['model']] = counts.get(change['model'], 0) + 1
        for model, count in counts.items():
            parts.append(text % {'count': count, 'what': _noun(env, model, count)})
    # Odoo has no ngettext: singular and plural are two separate translatable strings.
    if emails:
        n = len(emails)
        parts.append(_('queue %s email (not sent during the preview)', n) if n == 1
                     else _('queue %s emails (not sent during the preview)', n))
    if not parts:
        return ''
    listed = parts[0] if len(parts) == 1 else _('%(first)s and %(last)s', first=', '.join(parts[:-1]), last=parts[-1])
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
                'balanced': round(sum(line['debit'] for line in lines) - sum(line['credit'] for line in lines), 6) == 0,
            })
    return result


def _sections(env, model, method, res_ids, merged):
    """Extra tables from other modules (preview.mode.section); a broken extension is skipped."""
    result = []
    for section in env['preview.mode.section']._preview_sections(model, method, list(res_ids), merged):
        columns = [str(c) for c in section.get('columns', [])]
        rows = [[str(c) for c in row] for row in section.get('rows', [])]
        if rows:
            result.append({'title': str(section.get('title', '')), 'columns': columns, 'rows': rows})
    return result


def switched_on(env):
    """The administrator's kill switch: system parameter preview_mode.enabled, on unless set to false."""
    return param_bool(env, 'preview_mode.enabled', True)


# First key of the per-user advisory lock (second key is the user id).
LOCK_NAMESPACE = 0x70726576


def _skip_notice(env, model, res_ids):
    """Why this click is not previewed (shown to the user), or '' to preview it."""
    if not switched_on(env):
        return _('Preview Mode is switched off by your administrator.')
    limit = param_int(env, 'preview_mode.max_records')
    if limit and len(res_ids) > limit:
        return _('Too many records to preview (%(count)s, limit %(limit)s).', count=len(res_ids), limit=limit)
    return ''


def _flag_raw_writes(env, recorder, before):
    """Mark the preview incomplete when the click wrote to the database behind the ORM."""
    cr, uid, context = env.cr, env.uid, env.context  # noqa: F841 - read by _() to pick the language
    try:
        tables = unexplained(env, before, recorder.changes)
    except Exception:  # noqa: BLE001 - the safety check must not break the preview
        recorder.incomplete = True
        recorder.warnings.append(_('Could not check whether the click wrote to the database directly.'))
        return
    if tables:
        recorder.incomplete = True
        recorder.warnings.append(
            _('The click wrote directly to the database (%s). The preview cannot show those changes.', ', '.join(tables)))


def build_preview(env, model, method, res_ids, args, kwargs, label):
    """Same contract as call_button (args after the ids); no allow-list: any model, any method."""
    cr, uid, context = env.cr, env.uid, env.context  # noqa: F841 - read by _() to pick the language
    if model not in env or env[model]._abstract:
        # One error for unknown and abstract models, so the response cannot be used to list models.
        raise AccessError(_('Invalid model.'))
    notice = _skip_notice(env, model, res_ids)
    if notice:
        return {'show': False, 'notice': notice, 'changes': [], 'emails': [], 'warnings': [],
                'incomplete': False, 'summary': '', 'journal': [], 'sections': []}
    if method.startswith('_') or method == 'init':
        # Same rule as RPC: never run a private method (call_kw adds @api.private on 20).
        raise AccessError(_('Private methods cannot be previewed.'))
    if model in UNSAFE_MODELS or model.startswith(UNSAFE_PREFIXES):
        return {'show': False, 'changes': [], 'emails': [], 'warnings': [], 'incomplete': False,
                'summary': '', 'journal': [], 'sections': []}
    # One preview at a time per user (CWE-770). The lock lasts until the request's transaction ends; the
    # client then runs the click normally, exactly as when the preview is switched off.
    env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', (LOCK_NAMESPACE, env.uid))
    if not env.cr.fetchone()[0]:
        return {'show': False, 'notice': _('A preview is already running. This click ran without a preview.'),
                'changes': [], 'emails': [], 'warnings': [], 'incomplete': False, 'summary': '', 'journal': [], 'sections': []}
    warnings = []
    seconds = _timeout(env)
    timed_out = False
    # Translated before the run: after a cancelled query the transaction is unusable until rollback.
    timeout_text = _('The preview timed out after %s seconds. Confirming may still work.', seconds)
    with safe_run(env) as recorder:
        # SET LOCAL ends with the savepoint's rollback, so the normal timeout is back afterwards.
        env.cr.execute('SET LOCAL statement_timeout = %s', [int(seconds * 1000)])
        try:
            before = snapshot(env)
            # call_kw refuses private methods exactly like a real RPC would.
            call_kw(env[model], method, [list(res_ids), *args], kwargs)
            # Delayed writes (recomputed totals, states) only reach the recorder when flushed, and the
            # savepoint rollback drops them unflushed.
            env.flush_all()
            _flag_raw_writes(env, recorder, before)
        except UserError as e:  # also AccessError, ValidationError
            warnings.append({'text': _('Confirming will fail: %s', e.args[0] if e.args else e), 'blocking': True})
        except (PreviewBlocked, PreviewIncomplete):
            pass  # already recorded as incomplete by the guard
        except Exception as e:  # noqa: BLE001
            if getattr(e, 'pgcode', None) != '57014':  # query_canceled: the statement timeout hit
                raise
            timed_out = True
            recorder.incomplete = True
            recorder.warnings.append(timeout_text)
        try:
            journal = [] if timed_out else _journal(env, recorder.changes)
        except Exception:  # noqa: BLE001 - the extra view must never break the preview
            journal = []
        merged = _merge(recorder.changes)
        # Needs the records, so it runs before the rollback; menus are looked up once per model.
        menus, wheres = {}, []
        for change in merged[:MAX_ROWS]:
            if change['model'] not in menus:
                menus[change['model']] = candidates(env, change['model'])
            wheres.append(locate(env, change['model'], change['res_id'], menus[change['model']],
                                 recorder.deleted_values.get((change['model'], change['res_id']))))
        try:
            sections = [] if timed_out else _sections(env, model, method, res_ids, merged)
        except Exception:  # noqa: BLE001 - a third-party section must never break the preview
            sections = []
    # The savepoint is rolled back here; Change rows already hold plain text.
    warnings += [{'text': text, 'blocking': False} for text in recorder.warnings]
    changes = recorder.changes
    rows = []
    for change, where in zip(merged, wheres):
        rows.append({
            'kind': change['kind'],
            # Records without a real name show as "model,id"; say what they are instead.
            'what': env[change['model']]._description if change['what'] == '%s,%s' % (change['model'], change['res_id']) else change['what'],
            'where': where,
            'fields': [{'label': lbl, 'old': old, 'new': new} for lbl, (old, new) in change['fields'].items()],
        })
    if len(merged) > MAX_ROWS:
        rows.append({'kind': 'more', 'what': _('and %s more', len(merged) - MAX_ROWS), 'where': '', 'fields': []})
    blocking = [w for w in warnings if w['blocking']]
    summary = _summary(env, merged, recorder.emails)  # a blocking error is shown once, as a warning
    return {
        # The client decides on `show`, never on `changes == []`.
        'show': bool(rows or blocking or recorder.incomplete or recorder.emails or sections),
        'changes': rows,
        'emails': recorder.emails,
        'warnings': warnings,
        'incomplete': recorder.incomplete,
        'summary': summary,
        'journal': journal,
        'sections': sections,
    }
