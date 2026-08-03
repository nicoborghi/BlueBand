"""Parsers for the jury's shorthand input, and time formatting.

Three separators, consistent with the old track.py notation:

    sprints  "2,3,4,5-1,2,3,4"      `-` separates sprints, `,` the finish order
    heats    "1,2-3,4/5,6-7,8"      `/` separates heats, `-` opponents,
                                    `,` the riders of one team
    bibs     "7, 12, 3"             a flat list

Errors are raised as `ParseError` instead of blanking the page with an
uncaught ValueError, and the caller decides how to show them.
"""

from __future__ import annotations

import re

from .i18n import msg


class ParseError(ValueError):
    """Malformed jury input, with a message meant to be shown as-is."""


# ── bibs, sprints, heats ────────────────────────────────────────────────────

def _clean(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip(",-/")


def _bib(token: str, context: str = "") -> int:
    if not token:
        raise ParseError(msg("parse_missing_number", context=context))
    if not token.lstrip("+").isdigit():
        raise ParseError(msg("parse_bad_bib", token=token, context=context))
    return int(token)


def parse_bibs(text: str) -> list[int]:
    """Flat list of bibs from any of the three notations."""
    t = _clean(text)
    if not t:
        return []
    return [_bib(x) for x in re.split(r"[,\-/]", t) if x]


def parse_sprints(text: str) -> list[list[int]]:
    """`-`-separated sprints, each a `,`-separated finishing order."""
    t = _clean(text)
    if not t:
        return []
    out = []
    for i, chunk in enumerate(t.split("-")):
        if not chunk:
            continue
        where = msg("parse_in_sprint", n=i + 1)
        out.append([_bib(x, where) for x in chunk.split(",") if x])
    return out


def parse_heats(text: str) -> list[list[list[int]]]:
    """`/`-separated heats, each `-`-separated sides, each `,`-separated riders."""
    t = _clean(text)
    if not t:
        return []
    heats = []
    for i, h in enumerate(t.split("/")):
        if not h:
            continue
        sides = []
        for side in h.split("-"):
            if not side:
                continue
            where = msg("parse_in_heat", n=i + 1)
            sides.append([_bib(x, where) for x in side.split(",") if x])
        if sides:
            heats.append(sides)
    return heats


def format_heats(heats: list[list[list[int]]]) -> str:
    """Inverse of `parse_heats`, for pre-filling the input after seeding."""
    return "/".join("-".join(",".join(str(b) for b in side) for side in heat)
                    for heat in heats)


# ── validation helpers ──────────────────────────────────────────────────────

def duplicates(bibs: list[int]) -> list[int]:
    seen, dup = set(), []
    for b in bibs:
        if b in seen and b not in dup:
            dup.append(b)
        seen.add(b)
    return dup


def unknown(bibs: list[int], startlist: list[int]) -> list[int]:
    known = set(startlist)
    return sorted({b for b in bibs if b not in known})


# ── times ───────────────────────────────────────────────────────────────────

_TIME_RE = re.compile(
    r"^(?:(?P<h>\d+):)?(?:(?P<m>\d+):)?(?P<s>\d+)(?:[.,](?P<frac>\d{1,3}))?$")


def parse_time(text: str) -> int:
    """'3:31.370' / '03:31,370' / '34,67' -> milliseconds. Raises ParseError."""
    t = re.sub(r"\s+", "", str(text or ""))
    if not t:
        raise ParseError(msg("parse_missing_time"))
    m = _TIME_RE.match(t)
    if not m:
        raise ParseError(msg("parse_bad_time", text=repr(text)))
    h = int(m["h"] or 0)
    mins = int(m["m"] or 0)
    # a bare "m:ss" puts the minutes in the 'm' slot only when hours are absent
    if m["h"] and not m["m"]:
        h, mins = 0, h
    secs = int(m["s"])
    frac = (m["frac"] or "").ljust(3, "0")
    if secs >= 60 and (mins or h):
        raise ParseError(msg("parse_seconds_over_60", text=repr(text)))
    return ((h * 60 + mins) * 60 + secs) * 1000 + int(frac)


def format_time(ms: int | None, *, decimals: int = 3) -> str:
    """Milliseconds -> 'm:ss,mmm'as printed on the jury sheets."""
    if ms is None or ms < 0:
        return ""
    total, frac = divmod(int(ms), 1000)
    mins, secs = divmod(total, 60)
    frac_txt = f"{frac:03d}"[:decimals]
    base = f"{mins}:{secs:02d}" if mins else f"{secs}"
    return f"{base},{frac_txt}" if decimals else base


def parse_time_safe(text: str) -> tuple[int | None, str]:
    """(ms, error message) - never raises, for grid input."""
    try:
        return parse_time(text), ""
    except ParseError as exc:
        return None, str(exc)
