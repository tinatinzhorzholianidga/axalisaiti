"""Extraction markers for validator messages that live inside WTForms and
Flask-WTF. They are never executed; ``pybabel extract`` reads the literals so
the Georgian catalogue keeps a translation for every built-in message shown
to users (see :mod:`app.forms.base`)."""

from __future__ import annotations

from flask_babel import gettext as _
from flask_babel import ngettext


def _markers() -> None:  # pragma: no cover - never called
    _("Field must be equal to %(other_name)s.")
    ngettext(
        "Field must be at least %(min)d character long.",
        "Field must be at least %(min)d characters long.",
        1,
    )
    ngettext(
        "Field cannot be longer than %(max)d character.",
        "Field cannot be longer than %(max)d characters.",
        1,
    )
    ngettext(
        "Field must be exactly %(max)d character long.",
        "Field must be exactly %(max)d characters long.",
        1,
    )
    _("Field must be between %(min)d and %(max)d characters long.")
    _("Number must be at least %(min)s.")
    _("Number must be at most %(max)s.")
    _("Number must be between %(min)s and %(max)s.")
    _("This field is required.")
    _("Invalid input.")
    _("Invalid email address.")
    _("Invalid IP address.")
    _("Invalid Mac address.")
    _("Invalid URL.")
    _("Invalid UUID.")
    _("Invalid value, must be one of: %(values)s.")
    _("Invalid value, can't be any of: %(values)s.")
    _("This field cannot be edited.")
    _("This field is disabled and cannot have a value.")
    _("Invalid CSRF Token.")
    _("CSRF token missing.")
    _("CSRF failed.")
    _("CSRF token expired.")
    _("Invalid Choice: could not coerce.")
    _("Choices cannot be None.")
    _("Not a valid choice.")
    _("Invalid choice(s): one or more data inputs could not be coerced.")
    ngettext(
        "'%(value)s' is not a valid choice for this field.",
        "'%(value)s' are not valid choices for this field.",
        1,
    )
    _("Not a valid datetime value.")
    _("Not a valid date value.")
    _("Not a valid time value.")
    _("Not a valid week value.")
    _("Not a valid integer value.")
    _("Not a valid decimal value.")
    _("Not a valid float value.")
    # Flask-WTF
    _("The CSRF token is missing.")
    _("The CSRF session token is missing.")
    _("The CSRF token has expired.")
    _("The CSRF token is invalid.")
    _("The CSRF tokens do not match.")
    _("File does not have an approved extension: {extensions}")
    _("File does not have an approved extension.")
    _("File must be at least {size} bytes.")
    _("File must be at most {size} bytes.")
