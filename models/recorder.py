import threading
from typing import NamedTuple

from odoo import _

from .compat import has_access, old_column_values

IGNORED_MODELS = ('mail.tracking.value', 'mail.followers', 'mail.message', 'ir.attachment', 'mail.mail')
IGNORED_FIELDS = (
    'write_date', 'write_uid', 'create_date', 'create_uid',
    # Internal bookkeeping flags of Accounting, never meaningful to a person.
    'made_sequence_gap', 'is_manually_modified',
)
IGNORED_FIELD_SUFFIXES = ('_dirty',)
# Column fields whose old value can be read straight from the table (no translation, no JSON).
COLUMN_TYPES = ('boolean', 'integer', 'float', 'monetary', 'char', 'text', 'selection',
                'many2one', 'date', 'datetime')

from .formatting import display_value  # noqa: E402

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

    def __init__(self, uid=None):
        self.uid = uid  # the user who clicked; the mail addresses shown are limited to what they may read
        self.changes = []
        self.warnings = []
        self.emails = []
        self.queued_subjects = set()  # subjects of mail.mail records, so send_email does not count them twice
        self.incomplete = False
        self._previous = None
        self._formatted = {}  # (model, field, value) -> text, see _text

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

    def _text(self, record, name, value):
        field = record._fields[name]
        if field.type == 'many2one':
            return value[1] if value else ''
        if field.type == 'selection':
            return dict(field._description_selection(record.env)).get(value, '') if value else ''
        if field.type in ('one2many', 'many2many'):
            return ', '.join(record.env[field.comodel_name].browse(value).mapped('display_name'))
        if field.type != 'boolean' and (value is False or value is None):
            return ''
        if field.type in ('float', 'date', 'datetime'):
            # The same quantity, price or date repeats across the lines of one click: format it once.
            key = (record._name, name, value)
            if key not in self._formatted:
                self._formatted[key] = display_value(record, field, value) or str(value)
            return self._formatted[key]
        return display_value(record, field, value) or str(value)

    @staticmethod
    def _warm_names(records, names, rows):
        """Compute the display names of every x2many target of all rows in one batch per comodel,
        so the per-record text lookups below are cache hits instead of one query per record."""
        for name in names:
            field = records._fields[name]
            if field.type in ('one2many', 'many2many'):
                ids = {i for row in rows for i in row[name]}
                records.env[field.comodel_name].browse(ids).mapped('display_name')

    def _names(self, records, vals):
        return [n for n in vals
                if n not in IGNORED_FIELDS and not n.endswith(IGNORED_FIELD_SUFFIXES) and n in records._fields]

    def snapshot(self, records, vals):
        """Old values as text, {id: {field: text}}; never raises (a failure marks the recorder incomplete)."""
        if self._ignored(records):
            return None
        try:
            # Binary content is never read, only reported as changed.
            names = [n for n in self._names(records, vals) if records._fields[n].type != 'binary']
            if not names:
                return {}
            rows = records.read(names)
            self._warm_names(records, names, rows)
            return {row['id']: {n: self._text(records.browse(row['id']), n, row[n]) for n in names}
                    for row in rows}
        except Exception:  # noqa: BLE001 - must not break the write
            self.incomplete = True
            self.warnings.append('Could not read the previous values of %s' % records._name)
            return None

    def _note_mail(self, records):
        """A mail.mail row is an email the click queues; Odoo sends it after the commit, never in the preview."""
        try:
            user_env = records.env(su=False, user=self.uid or records.env.uid)
            for mail in records.sudo():  # sudo only to find the rows; addresses are filtered for the user below
                readable = has_access(user_env['mail.mail'].browse(mail.id), 'read')
                partners = user_env['res.partner'].browse(mail.recipient_ids.ids).filtered(
                    lambda p: has_access(p, 'read'))
                names = [mail.email_to] if readable and mail.email_to else []
                names += [p.email for p in partners if p.email]
                hidden = len(mail.recipient_ids) - len(partners) + (1 if mail.email_to and not readable else 0)
                if hidden:
                    names.append(_('%s hidden', hidden))
                self.emails.append({'to': ', '.join(names), 'subject': mail.subject or ''})
                self.queued_subjects.add(mail.subject or '')
        except Exception:  # noqa: BLE001 - must not break the create
            self.incomplete = True
            self.warnings.append('Could not read the emails this click queues')

    def snapshot_columns(self, records, vals_list):
        """Old values (read format text) of the plain column fields a flush is about to write.

        Odoo delays writes: recomputed stored fields (totals, states) reach the database through
        ``_write_multi``, not ``write``, and the cache already holds the new value, so the old one is
        read from the table. Returns ``(names, old)``; ``names`` is what ``note_write`` should compare.
        """
        if self._ignored(records):
            return [], None
        try:
            fields = [records._fields[n] for n in self._names(records, {k: 1 for v in vals_list for k in v})
                      if records._fields[n].store and not records._fields[n].translate
                      and not records._fields[n].company_dependent
                      and records._fields[n].type in COLUMN_TYPES]
            if not fields:
                return [], None
            rows = old_column_values(records.env.cr, records._table, [f.name for f in fields], records.ids)
            old = {}
            for row in rows:
                rec = records.browse(row[0])
                old[rec.id] = {
                    f.name: self._text(rec, f.name, f.convert_to_read(f.convert_to_record(f.convert_to_cache(value, rec), rec), rec))
                    for f, value in zip(fields, row[1:])}
            return [f.name for f in fields], old
        except Exception:  # noqa: BLE001 - must not break the flush
            self.incomplete = True
            self.warnings.append('Could not read the previous values of %s' % records._name)
            return [], None

    def note_create(self, records):
        if records._name == 'mail.mail':
            return self._note_mail(records)
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
            self._warm_names(records, names, new.values())
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
