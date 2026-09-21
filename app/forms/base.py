"""Shared form base: WTForms' built-in validator messages are looked up in the
platform's own gettext catalogue, so they follow the active locale (WTForms
ships no Georgian translations of its own)."""

from __future__ import annotations

from flask_babel import gettext, ngettext
from flask_wtf import FlaskForm


class CatalogTranslations:
    def gettext(self, string: str) -> str:
        return gettext(string)

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        return ngettext(singular, plural, n)


_translations = CatalogTranslations()


class BaseForm(FlaskForm):
    class Meta(FlaskForm.Meta):  # type: ignore[name-defined]
        def get_translations(self, form):  # type: ignore[no-untyped-def]
            return _translations
