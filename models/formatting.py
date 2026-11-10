"""Show a changed value the way the user's form shows it (amounts, numbers, dates)."""
from odoo import _
from odoo.tools.misc import (
    babel_locale_parse, format_amount, format_date, format_datetime, formatLang, get_lang, posix_to_ldml)


def _format_datetime(env, value):
    # PORT: on 16 to 19 format_datetime(..., 'medium') is babel's own style; Odoo 20 uses the
    # user's language date and time format. Passing that format explicitly gives the same on all.
    lang = get_lang(env)
    pattern = posix_to_ldml('%s %s' % (lang.date_format, lang.time_format), locale=babel_locale_parse(lang.code))
    return format_datetime(env, value, dt_format=pattern)


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
        return _format_datetime(env, value)
    return None
