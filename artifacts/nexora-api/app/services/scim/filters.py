"""Minimal SCIM filter parsing.

IdPs (Okta, Microsoft Entra) use SCIM filters almost exclusively to look up a
resource for matching before create, e.g. ``userName eq "x"`` or
``externalId eq "y"`` (and ``displayName eq "g"`` for groups). We parse exactly
that equality form and ignore anything else (callers then list unfiltered),
which is the documented, interoperable subset.
"""

from __future__ import annotations

import re

_EQ = re.compile(r'^\s*(?P<attr>[\w$.:]+)\s+eq\s+"(?P<value>(?:[^"\\]|\\.)*)"\s*$', re.IGNORECASE)


def parse_eq_filter(filter_str: str | None) -> tuple[str, str] | None:
    """Return ``(attribute, value)`` for an ``attr eq "value"`` filter, else None."""
    if not filter_str:
        return None
    match = _EQ.match(filter_str)
    if not match:
        return None
    attr = match.group("attr")
    value = match.group("value").replace('\\"', '"').replace("\\\\", "\\")
    return attr, value
