"""HTML sanitisation for instructor / admin authored rich content (nh3)."""

from __future__ import annotations

import nh3

ALLOWED_TAGS: set[str] = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "caption",
    "code",
    "dd",
    "del",
    "div",
    "dl",
    "dt",
    "em",
    "figcaption",
    "figure",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "ins",
    "kbd",
    "li",
    "mark",
    "ol",
    "p",
    "pre",
    "q",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
    "video",
    "source",
    "details",
    "summary",
}

ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "*": {"class", "id", "lang", "dir", "title"},
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height", "loading"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "video": {"src", "controls", "poster", "width", "height", "preload"},
    "source": {"src", "type"},
    "ol": {"start"},
    "code": {"data-lang"},
    "div": {"role", "data-callout"},
}

ALLOWED_URL_SCHEMES: set[str] = {"http", "https", "mailto"}

_ALLOWED_CLASS_PREFIXES = ("callout", "lesson-", "table", "text-", "code", "figure", "img-")


def _attribute_filter(tag: str, attr: str, value: str) -> str | None:
    if attr == "class":
        keep = [c for c in value.split() if c.startswith(_ALLOWED_CLASS_PREFIXES)]
        return " ".join(keep) if keep else None
    if attr == "target":
        return "_blank" if value == "_blank" else None
    if attr == "src" and tag in {"img", "video", "source"}:
        # Only same-origin media or absolute http(s) URLs; never data: for media.
        if value.startswith(("/", "http://", "https://")):
            return value
        return None
    return value


def sanitize_html(raw: str) -> str:
    if not raw:
        return ""
    return nh3.clean(
        raw,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
        strip_comments=True,
        attribute_filter=_attribute_filter,
    )


def strip_all_html(raw: str) -> str:
    return nh3.clean(raw or "", tags=set(), attributes={})
