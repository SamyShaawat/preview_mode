import threading
from typing import NamedTuple

IGNORED_MODELS = ('mail.tracking.value', 'mail.followers', 'mail.message', 'ir.attachment')
IGNORED_FIELDS = ('write_date', 'write_uid', 'create_date', 'create_uid')

_local = threading.local()


def active_recorder():
    return getattr(_local, 'recorder', None)


class Change(NamedTuple):
    kind: str  # 'new' | 'changed' | 'deleted'
    model: str
    res_id: int
    display_name: str
    fields: list  # [(field label, old text, new text)]


class ChangeRecorder:
    """Collects ORM changes made inside the ``with`` block."""

    def __init__(self):
        self.changes = []
        self.warnings = []
        self.emails = []
        self.incomplete = False
        self._previous = None

    def __enter__(self):
        self._previous = active_recorder()
        _local.recorder = self
        return self

    def __exit__(self, *exc):
        _local.recorder = self._previous
        return False

    @staticmethod
    def _ignored(records):
        return records._transient or records._name in IGNORED_MODELS

    @staticmethod
    def _text(record, name, value):
        field = record._fields[name]
        if field.type == 'many2one':
            return value[1] if value else ''
        if field.type == 'selection':
            return dict(field._description_selection(record.env)).get(value, '') if value else ''
        if field.type in ('one2many', 'many2many'):
            return ', '.join(record.env[field.comodel_name].browse(value).mapped('display_name'))
        return '' if value is False or value is None else str(value)

    def _names(self, records, vals):
        return [n for n in vals if n not in IGNORED_FIELDS and n in records._fields]

    def snapshot(self, records, vals):
        """Old values as text, {id: {field: text}}; never raises (a failure marks the recorder incomplete)."""
        if self._ignored(records):
            return None
        try:
            # Binary content is never read, only reported as changed.
            names = [n for n in self._names(records, vals) if records._fields[n].type != 'binary']
            if not names:
                return {}
            return {row['id']: {n: self._text(records.browse(row['id']), n, row[n]) for n in names}
                    for row in records.read(names)}
        except Exception:  # noqa: BLE001 - must not break the write
            self.incomplete = True
            self.warnings.append('Could not read the previous values of %s' % records._name)
            return None

    def note_create(self, records):
        if self._ignored(records):
            return
        for rec in records:
            self.changes.append(Change('new', rec._name, rec.id, rec.display_name, []))

    def note_write(self, records, old, vals):
        if old is None or self._ignored(records):
            return
        try:
            names = self._names(records, vals)
            binary = [n for n in names if records._fields[n].type == 'binary']
            names = [n for n in names if n not in binary]
            new = {row['id']: row for row in records.read(names)} if names else {}
            for rec in records:
                diffs = []
                for name in names:
                    before = old.get(rec.id, {}).get(name, '')
                    after = self._text(rec, name, new[rec.id][name])
                    if before != after:
                        diffs.append((rec._fields[name]._description_string(rec.env), before, after))
                diffs += [(rec._fields[n]._description_string(rec.env), '', '(changed)') for n in binary]
                if diffs:
                    self.changes.append(Change('changed', rec._name, rec.id, rec.display_name, diffs))
        except Exception:  # noqa: BLE001 - must not break the write
            self.incomplete = True
            self.warnings.append('Could not read the new values of %s' % records._name)

    def note_unlink(self, records):
        if self._ignored(records):
            return
        for rec in records:
            self.changes.append(Change('deleted', rec._name, rec.id, rec.display_name, []))
