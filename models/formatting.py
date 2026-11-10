"""Show a changed value the way the user's form shows it (amounts, numbers, dates)."""
from odoo import _
from odoo.tools.misc import format_amount, format_date, formatLang

from .compat import format_datetime_user


def display_value(record, field, value):
    """The value as the user's language and currency show it, or None to keep the plain text."""
    env = record.env
    if field.type == 'boolean':
        return _('Yes') if value else _('No')
    if field.type == 'monetary':
        currency = record[field.get_currency_field(record) or 'currency_id']
        if currency:
            return format_amount(env, value, currency)
    elif field.type == 'float':
        digits = field.get_digits(env)  # PORT: exists on Odoo 16 to 20
        if digits:
            return formatLang(env, value, digits=digits[1])
    elif field.type == 'date':
        return format_date(env, value)
    elif field.type == 'datetime':
        return format_datetime_user(env, value)
    return None
