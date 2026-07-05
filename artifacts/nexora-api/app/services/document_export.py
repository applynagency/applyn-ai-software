"""Sprint 44A — dependency-free document export.

Renders a Markdown-ish document into a valid, multi-page PDF (and a simple HTML
representation) without any third-party libraries. The PDF writer emits a
minimal but spec-compliant PDF 1.4 file using the built-in Helvetica font, so
``GET /v1/postmortems/{id}/export`` works in any environment.
"""

from __future__ import annotations

import html as _html

# Letter page geometry (points).
_PAGE_W = 612
_PAGE_H = 792
_MARGIN_X = 54
_TOP_Y = 740
_BOTTOM_Y = 54
_FONT_SIZE = 10
_LEADING = 14
_HEADING_SIZE = 15
_TITLE_SIZE = 20
_MAX_CHARS = 92  # wrap width for Helvetica 10pt within the text column
_LINES_PER_PAGE = int((_TOP_Y - _BOTTOM_Y) / _LEADING)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int) -> list[str]:
    text = text.rstrip()
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(w) > width:
            if cur:
                lines.append(cur)
                cur = ""
            while len(w) > width:
                lines.append(w[:width])
                w = w[width:]
            cur = w
            continue
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur or not lines:
        lines.append(cur)
    return lines


class _Line:
    __slots__ = ("text", "size", "indent")

    def __init__(self, text: str, size: int = _FONT_SIZE, indent: int = 0):
        self.text = text
        self.size = size
        self.indent = indent


def _markdown_to_lines(markdown: str) -> list[_Line]:
    """Flatten a Markdown subset (#, ##, ###, -, plain) into laid-out lines."""
    out: list[_Line] = []
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            out.append(_Line(""))
            continue
        if line.startswith("# "):
            for seg in _wrap(line[2:], _MAX_CHARS - 4):
                out.append(_Line(seg, size=_TITLE_SIZE))
            out.append(_Line(""))
        elif line.startswith("## "):
            out.append(_Line(""))
            for seg in _wrap(line[3:], _MAX_CHARS - 4):
                out.append(_Line(seg, size=_HEADING_SIZE))
        elif line.startswith("### "):
            for seg in _wrap(line[4:], _MAX_CHARS - 4):
                out.append(_Line(seg, size=12))
        elif line.lstrip().startswith(("- ", "* ")):
            stripped = line.lstrip()
            content = stripped[2:]
            wrapped = _wrap(content, _MAX_CHARS - 4)
            out.append(_Line("\u2022 " + wrapped[0], indent=12))
            for seg in wrapped[1:]:
                out.append(_Line("  " + seg, indent=12))
        else:
            for seg in _wrap(line, _MAX_CHARS):
                out.append(_Line(seg))
    return out


def _paginate(lines: list[_Line]) -> list[list[_Line]]:
    pages: list[list[_Line]] = []
    cur: list[_Line] = []
    count = 0
    for ln in lines:
        # Headings consume a little more vertical room; treat title as 2 lines.
        cost = 2 if ln.size >= _HEADING_SIZE else 1
        if count + cost > _LINES_PER_PAGE:
            pages.append(cur)
            cur = []
            count = 0
        cur.append(ln)
        count += cost
    if cur:
        pages.append(cur)
    return pages or [[_Line("")]]


def _content_stream(page_lines: list[_Line]) -> bytes:
    parts = ["BT", f"/F1 {_FONT_SIZE} Tf", f"{_LEADING} TL", f"{_MARGIN_X} {_TOP_Y} Td"]
    cur_size = _FONT_SIZE
    for ln in page_lines:
        if ln.size != cur_size:
            parts.append(f"/F1 {ln.size} Tf")
            cur_size = ln.size
        x = ln.indent
        if x:
            parts.append(f"{x} 0 Td")
        parts.append(f"({_pdf_escape(ln.text)}) Tj")
        if x:
            parts.append(f"{-x} 0 Td")
        parts.append("T*")
    parts.append("ET")
    return ("\n".join(parts) + "\n").encode("latin-1", "replace")


def render_pdf(markdown: str) -> bytes:
    """Produce a valid multi-page PDF from a Markdown document."""
    pages = _paginate(_markdown_to_lines(markdown))
    n_pages = len(pages)

    # Object numbering: 1=Catalog, 2=Pages, 3=Font, then per page: page obj + content obj.
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    page_obj_ids = []
    content_obj_ids = []
    base = 4  # objects 4.. are pages/contents
    for i in range(n_pages):
        page_obj_ids.append(base + i * 2)
        content_obj_ids.append(base + i * 2 + 1)
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("latin-1"))

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Build page + content objects in order, keyed by their object id.
    obj_by_id: dict[int, bytes] = {}
    for i, page_lines in enumerate(pages):
        pid = page_obj_ids[i]
        cid = content_obj_ids[i]
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_W} {_PAGE_H}] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        ).encode("latin-1")
        obj_by_id[pid] = page_dict
        stream = _content_stream(page_lines)
        content = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"
        obj_by_id[cid] = content

    # Assemble file with xref offsets.
    out = bytearray()
    out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = {0: 0}

    def write_obj(num: int, body: bytes):
        offsets[num] = len(out)
        out.extend(f"{num} 0 obj\n".encode("latin-1"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    write_obj(1, objects[0])
    write_obj(2, objects[1])
    write_obj(3, objects[2])
    for num in sorted(obj_by_id):
        write_obj(num, obj_by_id[num])

    total_objs = 3 + len(obj_by_id)
    xref_pos = len(out)
    out.extend(f"xref\n0 {total_objs + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for num in range(1, total_objs + 1):
        out.extend(f"{offsets.get(num, 0):010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer\n<< /Size {total_objs + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode(
            "latin-1"
        )
    )
    return bytes(out)


def render_html(title: str, markdown: str) -> str:
    """Render the Markdown subset into a self-contained, printable HTML doc."""
    body: list[str] = []
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            body.append(f"<h1>{_html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            close_list()
            body.append(f"<h2>{_html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            close_list()
            body.append(f"<h3>{_html.escape(line[4:])}</h3>")
        elif line.lstrip().startswith(("- ", "* ")):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_html.escape(line.lstrip()[2:])}</li>")
        else:
            close_list()
            body.append(f"<p>{_html.escape(line)}</p>")
    close_list()
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_html.escape(title)}</title>"
        "<style>body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        "max-width:820px;margin:40px auto;padding:0 24px;color:#1e293b;line-height:1.5;}"
        "h1{font-size:26px;border-bottom:2px solid #e2e8f0;padding-bottom:8px;}"
        "h2{font-size:18px;margin-top:28px;color:#0f172a;}h3{font-size:14px;}"
        "ul{margin:6px 0 6px 4px;}li{margin:3px 0;}p{margin:6px 0;}</style></head><body>"
        + "\n".join(body)
        + "</body></html>"
    )
