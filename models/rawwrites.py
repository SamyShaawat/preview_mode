"""Find database writes the ORM recorder did not see (raw SQL, triggers, bulk statements).

PostgreSQL keeps per-transaction row counters (``pg_stat_xact_user_tables``). A preview reads them
before and after the click. A table whose counters moved without a matching recorder entry was
written behind the ORM's back, so the preview cannot be complete.

Known limit: a raw UPDATE on a table the ORM also wrote in the same click is not caught.
"""
from .recorder import IGNORED_MODELS

QUERY = "SELECT relname, n_tup_ins, n_tup_upd, n_tup_del FROM pg_stat_xact_user_tables"


def snapshot(env):
    """Row counters of this transaction so far, {table: (inserted, updated, deleted)}."""
    env.cr.execute(QUERY)
    return {table: (ins, upd, dele) for table, ins, upd, dele in env.cr.fetchall()}


def _relation_tables(model):
    return {f.relation for f in model._fields.values() if f.type == 'many2many' and f.store and f.relation}


def _cascaded(env, deleted_models):
    """Tables the database changes by itself when the recorded records are deleted.

    Returns (tables whose rows are deleted by a foreign key cascade, tables updated by a set null).
    """
    cascade, set_null = set(), set()
    visited = set()  # model names already followed; mutual cascades would loop forever without it
    frontier = set(deleted_models)
    while frontier:
        found = set()
        for name in env.registry:
            model = env[name]
            if not model._auto or model._abstract or name in visited:
                continue
            for field in model._fields.values():
                if field.type == 'many2many' or not (field.type == 'many2one' and field.store):
                    continue
                if field.comodel_name in frontier and field.ondelete in ('cascade', 'set null'):
                    (cascade if field.ondelete == 'cascade' else set_null).add(model._table)
                    if field.ondelete == 'cascade':
                        found.add(name)
        visited |= found
        frontier = found
    return cascade, set_null


def unexplained(env, before, changes):
    """Sorted names of tables written without a recorder entry that accounts for it."""
    after = snapshot(env)
    zero = (0, 0, 0)
    moved = {t: tuple(a - b for a, b in zip(v, before.get(t, zero))) for t, v in after.items() if v != before.get(t, zero)}
    if not moved:
        return []
    table_of = {name: env[name]._table for name in env.registry if env[name]._auto and not env[name]._abstract}
    model_of = {table: name for name, table in table_of.items()}
    seen = {}  # (table, kind) -> records the recorder saw
    for change in changes:
        key = (table_of[change.model], change.kind)
        seen[key] = seen.get(key, 0) + 1
    recorded = {table for table, _kind in seen}
    # Tables the recorder ignores on purpose (mail, attachments, wizards) and every many2many link table.
    free = {table_of[n] for n in IGNORED_MODELS if n in table_of}
    free |= {table_of[n] for n in table_of if env[n]._transient}
    links = set()
    for name in table_of:
        if name in IGNORED_MODELS or name in {c.model for c in changes} or env[name]._transient:
            links |= _relation_tables(env[name])
    cascade_tables, null_tables = _cascaded(env, {c.model for c in changes if c.kind == 'deleted'})
    bad = []
    for table, (ins, upd, dele) in moved.items():
        if table in free or table in links:
            continue
        if table not in model_of:
            bad.append(table)  # a table no model owns: only raw SQL touches it
        elif ins != seen.get((table, 'new'), 0):
            bad.append(table)
        elif dele and table not in cascade_tables and dele != seen.get((table, 'deleted'), 0):
            bad.append(table)
        elif upd and table not in recorded and table not in null_tables:
            bad.append(table)
    return sorted(bad)
