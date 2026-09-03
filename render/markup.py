"""The little markdown the jury can type into a sheet.

One place in the app takes prose rather than a field: the *foglio intestato*,
which is the letterhead with a text under it - a convocazione, a nota di
servizio, whatever has to go out on the paper of the meeting without being a
classifica. Prose that cannot be emphasised is prose nobody reads, so the box
takes markdown; and a full markdown library is a dependency the Windows build
would have to freeze for four constructs.

So: four constructs and no more, and everything else is text.

    # ## ###     headings
    **bold**  *italic*  `code`
    - item      bullets (also `*` and `+`)
    1. item     numbers
    ---         a rule
    blank line  a new paragraph; a single newline is a line break

**Everything is escaped before anything is read.** What the jury types is text,
never markup: a sheet that renders an `<img>` somebody pasted into the box is a
sheet that can be made to say anything.
"""

from __future__ import annotations

import re
from html import escape

#: `**bold**` before `*italic*`, or the first would eat the stars of the second.
_INLINE = (
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*(\S(?:.*?\S)?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"__(\S(?:.*?\S)?)__"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*(\S(?:.*?\S)?)\*(?![\w*])"), r"<em>\1</em>"),
    (re.compile(r"(?<![\w_])_(\S(?:.*?\S)?)_(?![\w_])"), r"<em>\1</em>"),
)

_BULLET = re.compile(r"^[-*+]\s+(.*)$")
_NUMBER = re.compile(r"^\d+[.)]\s+(.*)$")
_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_RULE = re.compile(r"^\s*(?:-{3,}|_{3,}|\*{3,})\s*$")


def inline(text: str) -> str:
    """One line of text, escaped, with the emphasis marks read."""
    out = escape(text.strip())
    for pattern, repl in _INLINE:
        out = pattern.sub(repl, out)
    return out


def to_html(text: str) -> str:
    """The markdown subset above as HTML, or '' for an empty box.

    Block by block: a blank line closes whatever is open, which is the one rule
    that keeps a list from swallowing the paragraph under it.
    """
    if not (text or "").strip():
        return ""
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []
    tag = ""

    def close() -> None:
        nonlocal tag
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()
        if items:
            out.append(f"<{tag}>" + "".join(f"<li>{i}</li>" for i in items)
                       + f"</{tag}>")
            items.clear()
        tag = ""

    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            close()
            continue
        if _RULE.match(line):
            close()
            out.append("<hr>")
            continue
        head = _HEADING.match(line.strip())
        if head:
            close()
            level = len(head.group(1)) + 2   # the sheet's own title is the h1
            out.append(f"<h{level}>{inline(head.group(2))}</h{level}>")
            continue
        bullet = _BULLET.match(line.strip())
        number = _NUMBER.match(line.strip())
        if bullet or number:
            wanted = "ul" if bullet else "ol"
            if tag != wanted:
                close()
                tag = wanted
            items.append(inline((bullet or number).group(1)))
            continue
        if items:
            # text under a list item, not a new paragraph of its own
            items[-1] += "<br>" + inline(line)
            continue
        para.append(inline(line))
    close()
    return "\n".join(out)
