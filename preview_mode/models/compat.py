"""Everything that differs between Odoo versions lives here, so the rest of the core is shared.

This is the Odoo 16.0 flavour. The same module on 20.0 reads parameters with get_str/get_int/get_float/get_bool,
uses odoo.tools.SQL and has_access.
"""
from odoo.exceptions import AccessError


def has_access(records, operation):
    # PORT: has_access exists on Odoo 18+; 16 and 17 need the rights + rules pair.
    if not records.check_access_rights(operation, raise_exception=False):
        return False
    try:
        records.check_access_rule(operation)
    except AccessError:
        return False
    return True


def param_float(env, key):
    # PORT: Odoo 20 has get_float; on 16 to 19 get_param returns text, or False when unset.
    try:
        return float(env['ir.config_parameter'].sudo().get_param(key) or 0)
    except ValueError:
        return 0.0


def param_int(env, key):
    # PORT: Odoo 20 has get_int.
    try:
        return int(float(env['ir.config_parameter'].sudo().get_param(key) or 0))
    except ValueError:
        return 0


def param_bool(env, key, default):
    # PORT: Odoo 20 has get_bool; here only the text 'False' (any case) or '0' switches it off.
    value = env['ir.config_parameter'].sudo().get_param(key)
    if value is False or value is None or value == '':
        return default
    return str(value).strip().lower() not in ('false', '0')


def set_param(env, key, value):
    # PORT: Odoo 20 has set_str; used by the tests.
    env['ir.config_parameter'].sudo().set_param(key, value)


def old_column_values(cr, table, names, ids):
    """Rows ``(id, *values)`` of the given plain columns, read straight from the table."""
    # PORT: Odoo 17 to 20 build this with odoo.tools.SQL; on 16 a quoted query with %s parameters.
    # Names come from the model registry, never from user input.
    columns = ', '.join('"%s"' % name for name in ['id'] + list(names))
    cr.execute('SELECT %s FROM "%s" WHERE id IN %%s' % (columns, table), [tuple(ids)])
    return cr.fetchall()


def format_datetime_user(env, value):
    """A datetime the way the user's language writes it (date and time format of the language)."""
    # PORT: Odoo 16 formats 'medium' with babel ("Jan 31, 2026, 10:00:00 AM"); dt_format=False
    # gives the language's own date and time format. 17 to 20 use the language format by default.
    from odoo.tools.misc import format_datetime
    return format_datetime(env, value, dt_format=False)
