"""Slack message formatting utilities."""

import json
import logging
import re
import uuid

logger = logging.getLogger(__name__)

SLACK_MAX_TEXT_LENGTH = 3000
SLACK_MAX_BLOCKS = 50
# chat.postMessage can reject an exactly-50-block message with `msg_blocks_too_long`
# even though every individual block is under SLACK_MAX_TEXT_LENGTH — this is a
# separate, undocumented aggregate-size check distinct from the per-block 3000-char
# limit and the 50-block count limit (confirmed live: 50 blocks / ~22,162 bytes of
# serialized JSON was rejected). Chunking on total serialized size too, with a
# generous safety margin below that confirmed-failing size, avoids relying on an
# unknown exact threshold.
SLACK_MAX_TOTAL_PAYLOAD_CHARS = 10_000

# Column name hints for smart number formatting
_CURRENCY_HINTS = {
    "balance",
    "amount",
    "price",
    "cost",
    "revenue",
    "total",
    "fee",
    "payment",
    "salary",
    "profit",
    "loss",
    "value",
    "spend",
    "budget",
}
_PCT_HINTS = {"pct", "percent", "rate", "ratio", "share"}

_non_ascii_re = re.compile(r"[^\x00-\x7F]+")

# SQL keyword detection — used to auto-fence bare SQL queries in monospaced blocks
_SQL_RE = re.compile(
    r"^(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP|ALTER|EXPLAIN)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Emoji → ASCII substitutions applied to table cells before monospace alignment
_EMOJI_NORM: list[tuple[str, str]] = [
    ("✅", "Yes"),
    ("☑️", "Yes"),
    ("✓", "Yes"),
    ("❌", "No"),
    ("✗", "No"),
    ("🟢", "OK"),
    ("🔴", "FAIL"),
    ("🟡", "WARN"),
    ("⚠️", "WARN"),
    ("⭕", "-"),
]


def _normalise_cell(text: str) -> str:
    """Strip emojis and non-ASCII from a table cell; return '—' if empty."""
    for emoji, replacement in _EMOJI_NORM:
        text = text.replace(emoji, replacement)
    return _non_ascii_re.sub("", text).strip() or "—"


# ── Visual enrichment helpers ──────────────────────────────────────────────────

# Keywords → emoji prefix for section headings
_HEADER_EMOJI_MAP: list[tuple[str, str]] = [
    ("key takeaway", ":bulb:"),
    ("takeaway", ":bulb:"),
    ("insight", ":bulb:"),
    ("recommendation", ":pushpin:"),
    ("next step", ":arrow_right:"),
    ("action item", ":zap:"),
    ("summary", ":bar_chart:"),
    ("overview", ":eyes:"),
    ("report", ":memo:"),
    ("finding", ":mag:"),
    ("analysis", ":mag:"),
    ("result", ":clipboard:"),
    ("warning", ":warning:"),
    ("alert", ":warning:"),
    ("important", ":exclamation:"),
    ("error", ":x:"),
    ("fail", ":x:"),
    ("success", ":white_check_mark:"),
    ("complete", ":white_check_mark:"),
    ("migration", ":arrows_counterclockwise:"),
    ("worker", ":gear:"),
    ("job", ":briefcase:"),
    ("status", ":traffic_light:"),
    ("performance", ":racing_car:"),
    ("security", ":lock:"),
    ("revenue", ":moneybag:"),
    ("cost", ":moneybag:"),
    ("growth", ":chart_with_upwards_trend:"),
    ("trend", ":chart_with_upwards_trend:"),
    ("database", ":floppy_disk:"),
    ("user", ":bust_in_silhouette:"),
]

# Prefixes that mark a line as a footnote-style context annotation
_CONTEXT_PREFIXES = ("note:", "source:", "data from:", "powered by:", "as of ", "last updated", "via ")


def _auto_emoji_header(text: str) -> str:
    """Return an emoji prefix for a heading based on keyword matching.

    Returns empty string if the heading already starts with an emoji/symbol.
    """
    if re.match(r"^[^\w\s]", text):  # already starts with emoji or punctuation
        return ""
    lower = text.lower()
    for keyword, emoji in _HEADER_EMOJI_MAP:
        if keyword in lower:
            return emoji + " "
    return ""


def _parse_inline_elements(text: str) -> list[dict]:
    """Convert markdown inline formatting into Slack rich_text element objects."""
    elements: list[dict] = []
    pattern = re.compile(r"\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|`([^`\n]+)`|\[([^\]]+)\]\(([^)]+)\)")
    last = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            elements.append({"type": "text", "text": text[last : m.start()]})
        if m.group(1):  # **bold**
            elements.append({"type": "text", "text": m.group(1), "style": {"bold": True}})
        elif m.group(2):  # *bold* (Slack uses * for bold)
            elements.append({"type": "text", "text": m.group(2), "style": {"bold": True}})
        elif m.group(3):  # `code`
            elements.append({"type": "text", "text": m.group(3), "style": {"code": True}})
        elif m.group(4):  # [text](url)
            elements.append({"type": "link", "url": m.group(5), "text": m.group(4)})
        last = m.end()
    if last < len(text):
        elements.append({"type": "text", "text": text[last:]})
    return elements or [{"type": "text", "text": text}]


_BULLET_LINE_RE = re.compile(r"^[•\-\*]\s+(.*)$")
_ORDERED_LINE_RE = re.compile(r"^\d+[.)]\s+(.*)$")


def _to_rich_text_list(lines: list[str], style: str) -> dict:
    """Build a Slack rich_text block containing a bullet or ordered list."""
    strip_re = re.compile(r"^(?:[•\-\*]|\d+[.)]) +")
    items = []
    for line in lines:
        content = strip_re.sub("", line.strip())
        if content:
            items.append(
                {
                    "type": "rich_text_section",
                    "elements": _parse_inline_elements(content),
                }
            )
    return {
        "type": "rich_text",
        "elements": [{"type": "rich_text_list", "style": style, "indent": 0, "elements": items}],
    }


def _is_numeric_col(values: list[str]) -> bool:
    """Return True if ≥80 % of non-empty column values are numeric."""
    total = valid = 0
    for v in values:
        if v and v != "—":
            total += 1
            try:
                float(re.sub(r"[$,%]", "", v))
                valid += 1
            except ValueError:
                pass
    return total > 0 and valid / total >= 0.8


def _fmt_number(value: str, col_name: str) -> str:
    """Format a numeric string with commas, currency prefix, or % suffix."""
    col = col_name.lower()
    try:
        cleaned = re.sub(r"[$,%]", "", value).strip()
        if not cleaned:
            return value
        num = float(cleaned)

        # Percentage column
        if any(h in col for h in _PCT_HINTS):
            return f"{num:.1f}%"

        # Currency column
        if any(h in col for h in _CURRENCY_HINTS):
            if num.is_integer():
                return f"${int(num):,}"
            # Crypto-scale small values — strip trailing zeros
            if 0 < abs(num) < 0.001:
                return "$" + f"{num:.8f}".rstrip("0")
            return f"${num:,.2f}"

        # Integer-like
        if num.is_integer():
            return f"{int(num):,}"

        # Small decimal (crypto balances, rates)
        if 0 < abs(num) < 0.01:
            return f"{num:.8f}"

        # Large float
        if abs(num) >= 1000:
            return f"{num:,.2f}"

        return str(num)
    except (ValueError, OverflowError):
        return value


# Auto-inject emojis for common status / value words in table cells.
# Checked against the lowercased cell value — first match wins.
_STATUS_EMOJI: list[tuple[str, str]] = [
    ("locked", ":lock:"),
    ("unlocked", ":unlock:"),
    ("connected", ":large_green_circle:"),
    ("disconnected", ":red_circle:"),
    ("active", ":large_green_circle:"),
    ("inactive", ":white_circle:"),
    ("completed", ":white_check_mark:"),
    ("failed", ":x:"),
    ("pending", ":hourglass_flowing_sand:"),
    ("in progress", ":arrows_counterclockwise:"),
    ("good", ":star:"),
    ("excellent", ":star2:"),
    ("poor", ":thumbsdown:"),
    ("100%", ":battery:"),
    ("success", ":white_check_mark:"),
    ("error", ":x:"),
    ("warning", ":warning:"),
]


def _apply_emoji_status(text: str) -> str:
    """Prepend a relevant emoji when a cell value matches a known status word."""
    lower = text.strip().lower()
    for keyword, emoji in _STATUS_EMOJI:
        if lower == keyword or lower.startswith(keyword):
            return f"{emoji} {text}"
    return text


def format_text_for_slack(text: str) -> str:
    """Convert markdown text to Slack mrkdwn format.

    Used as the plain-text fallback for Block Kit messages and for
    direct Slack tool calls (slack_tools.py).
    """
    logger.debug("Converting markdown to Slack format")

    # --- Protect code blocks from subsequent transformations ---
    code_map: dict[str, str] = {}

    def _extract_code(match: re.Match) -> str:
        token = f"CODEBLOCK_{uuid.uuid4().hex}"
        code_map[token] = match.group(0)
        return token

    text = re.sub(r"(```[\s\S]+?```|`[^`\n]+?`)", _extract_code, text)

    # --- Clean HTML artifacts the LLM sometimes emits ---
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p\s*/?>", "\n", text, flags=re.IGNORECASE)

    # --- Convert @USER_ID → Slack mention ---
    text = re.sub(r"(?<!<)@([UW][A-Z0-9]+)(?!>)", r"<@\1>", text)

    # --- Headers → bold (H1/H2 get header blocks in create_slack_blocks) ---
    text = re.sub(r"^\s*#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)

    # --- Bold ---
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)

    # --- Lists (nested first, then top-level) ---
    text = re.sub(r"^\s{2,}(?:[-*]|\d+[.)])\s+", "  • ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s+-\s+(.*)$", r"  • \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s+•", "  •", text, flags=re.MULTILINE)

    # --- Links: [text](url) → <url|text> ---
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

    # --- Clean up stray double-stars ---
    text = text.replace("**", "*")

    # --- Restore code blocks ---
    for token, original in code_map.items():
        text = text.replace(token, original)

    logger.debug("Markdown conversion complete")
    return text


def clean_table_cell(text: str) -> str:
    """Sanitise a markdown table cell value for display in Slack."""
    # HTML line breaks → space (common LLM table artifact)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    # Strip broken image references like ![Profile Picture] or ![alt](non-http-url)
    text = re.sub(r"!\[([^\]]*)\](?:\([^)]*\))?", r"\1", text)
    # Strip markdown bold / italic / code markers
    text = re.sub(r"[*_`]", "", text)
    # Collapse markdown links to their display text
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    return text.strip()


def convert_markdown_table_to_slack_blocks(markdown_table: str) -> list:
    """Convert a markdown table to Slack Block Kit blocks.

    2-column (key | value) tables are rendered using section *fields* — Slack's
    native two-column grid, which looks far better than pipe-separated plain text.

    Multi-column tables fall back to a monospaced-style text block with a bold
    header row and unicode box-drawing separators.
    """
    lines = [line.strip() for line in markdown_table.strip().split("\n")]

    headers: list[str] = []
    data: list[list[str]] = []

    for line in lines:
        if "|" not in line:
            continue

        cells = [c.strip() for c in line.split("|")]
        if line.startswith("|") and cells:
            cells.pop(0)
        if line.endswith("|") and cells:
            cells.pop()

        # Separator row (---|---) → skip
        if cells and all(re.match(r"^[-:\s]+$", c) for c in cells if c):
            continue

        clean_cells = [clean_table_cell(c) for c in cells]
        if not any(clean_cells):
            continue

        if not headers:
            headers = clean_cells
        else:
            if len(clean_cells) < len(headers):
                clean_cells += [""] * (len(headers) - len(clean_cells))
            data.append(clean_cells[: len(headers)])

    if not headers or not data:
        return []

    blocks: list[dict] = []

    if len(headers) == 2:
        # ── Key-value table → section fields (native Slack 2-col grid) ──────
        fields = []
        for row in data:
            key = row[0] if row else ""
            val = _apply_emoji_status(row[1] if len(row) > 1 else "")
            if key:
                # Truncate very long values so they don't overflow a field
                if len(val) > 300:
                    val = val[:297] + "…"
                fields.append({"type": "mrkdwn", "text": f"*{key}*\n{val}"})

        # Slack allows max 10 fields per section block
        for i in range(0, len(fields), 10):
            chunk = fields[i : i + 10]
            blocks.append({"type": "section", "fields": chunk})
            if i + 10 < len(fields):
                blocks.append({"type": "divider"})

    else:
        # ── Multi-column table → code block (monospaced = guaranteed alignment) ──
        norm_headers = [_normalise_cell(h) for h in headers]
        # Replace empty/null cells with em-dash
        norm_data = [[_normalise_cell(c) if c.strip() else "—" for c in row] for row in data]

        # Detect numeric columns for formatting + right-alignment
        num_cols: list[bool] = []
        for j, _hdr in enumerate(norm_headers):
            col_vals = [row[j] for row in norm_data if j < len(row)]
            num_cols.append(_is_numeric_col(col_vals))

        # Apply number formatting to numeric columns
        for row in norm_data:
            for j, cell in enumerate(row):
                if j < len(num_cols) and num_cols[j] and cell != "—":
                    row[j] = _fmt_number(cell, norm_headers[j])

        col_widths = [len(h) for h in norm_headers]
        for row in norm_data:
            for j, cell in enumerate(row):
                if j < len(col_widths):
                    col_widths[j] = max(col_widths[j], len(cell))

        col_sep = "  "

        def _fmt_row(cells: list[str], is_header: bool = False) -> str:
            parts = []
            for j, cell in enumerate(cells):
                w = col_widths[j] if j < len(col_widths) else len(cell)
                # Right-align numeric columns, left-align everything else
                if not is_header and j < len(num_cols) and num_cols[j]:
                    parts.append(cell.rjust(w))
                else:
                    parts.append(cell.ljust(w))
            return col_sep.join(parts)

        separator = col_sep.join("─" * w for w in col_widths)
        table_lines = [_fmt_row(norm_headers, is_header=True), separator]
        for row in norm_data:
            table_lines.append(_fmt_row(row))

        # Chunk at SLACK_MAX_TEXT_LENGTH, always keeping header + separator.
        # Track running char count (O(n)) rather than re-joining the full list each row (O(n²)).
        # +6 accounts for the ``` fences wrapping the final table_text.
        chunk_lines: list[str] = [table_lines[0], table_lines[1]]
        # header len + \n + separator len
        current_len = len(table_lines[0]) + 1 + len(table_lines[1])
        total_rows = len(norm_data)
        rows_added = 0
        for row_line in table_lines[2:]:
            added = 1 + len(row_line)  # leading \n + line content
            if current_len + added + 6 > SLACK_MAX_TEXT_LENGTH:
                chunk_lines.append(f"… {total_rows - rows_added} more rows")
                break
            chunk_lines.append(row_line)
            current_len += added
            rows_added += 1

        table_text = "\n".join(chunk_lines)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"```{table_text}```"}})

    return blocks


def _image_block(alt: str, url: str) -> dict:
    return {"type": "image", "image_url": url, "alt_text": alt or "image"}


def _chunk_code_block(fenced_text: str) -> list[dict]:
    """Split an already-```-fenced code block into section blocks under SLACK_MAX_TEXT_LENGTH.

    LLMs frequently return large fenced blocks for this kind of request (mermaid
    flowcharts, full file dumps, etc.) that alone exceed Slack's per-block 3000-char
    text limit. Unlike regular text sections (chunked below), this path previously
    emitted the whole fenced block as a single section with no length check, which
    Slack's chat.postMessage rejects outright with `invalid_blocks` — silently
    failing the entire response instead of just wrapping. Line-based chunking keeps
    each Slack block valid mrkdwn (i.e. never splits a fence marker across blocks).
    """
    if len(fenced_text) <= SLACK_MAX_TEXT_LENGTH:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": fenced_text}}]

    match = re.match(r"^```(\w*)\n([\s\S]*?)\n?```$", fenced_text)
    if not match:
        chunks = [fenced_text[i : i + SLACK_MAX_TEXT_LENGTH] for i in range(0, len(fenced_text), SLACK_MAX_TEXT_LENGTH)]
        return [{"type": "section", "text": {"type": "mrkdwn", "text": c}} for c in chunks]

    lang, body = match.group(1), match.group(2)
    fence_overhead = len(f"```{lang}\n") + len("\n```")
    max_body_len = SLACK_MAX_TEXT_LENGTH - fence_overhead

    def _wrap(lines: list[str]) -> dict:
        return {"type": "section", "text": {"type": "mrkdwn", "text": f"```{lang}\n" + "\n".join(lines) + "\n```"}}

    blocks: list[dict] = []
    current_lines: list[str] = []
    current_len = 0
    for line in body.split("\n"):
        # A single line longer than the budget must be hard-sliced on its own.
        while len(line) > max_body_len:
            if current_lines:
                blocks.append(_wrap(current_lines))
                current_lines, current_len = [], 0
            blocks.append(_wrap([line[:max_body_len]]))
            line = line[max_body_len:]

        added = len(line) + 1
        if current_lines and current_len + added > max_body_len:
            blocks.append(_wrap(current_lines))
            current_lines, current_len = [], 0
        current_lines.append(line)
        current_len += added

    if current_lines:
        blocks.append(_wrap(current_lines))

    return blocks


def create_slack_blocks(text: str) -> list:
    """Parse raw LLM markdown and produce Slack Block Kit blocks.

    Improvements over plain text:
    - 2-col markdown tables → section fields (native Slack grid)
    - Multi-col tables      → bold header + unicode separator rows
    - H1/H2 headings        → header blocks (larger, prominent title)
    - H3-H6 headings        → bold section text
    - ![alt](url) images    → inline image blocks (actually displayed)
    - <br> tags             → newlines (not literal HTML)
    - Status values         → auto-prefixed with relevant emoji
    """
    blocks: list[dict] = []

    # ── Pre-pass: extract markdown images so they survive table splitting ───
    # NOTE: <br> is intentionally NOT replaced here — doing so before table splitting
    # would break multi-value cells like "Name <br> Email: x". clean_table_cell()
    # replaces <br> with a space inside tables; format_text_for_slack() replaces
    # it with \n in regular text sections. Both run after the table split below.
    # Replace ![alt](url) with a sentinel; we'll emit image blocks for each.
    _img_sentinel = "SLACK_IMG_"
    _img_map: dict[str, tuple[str, str]] = {}

    def _extract_image(m: re.Match) -> str:
        key = f"{_img_sentinel}{uuid.uuid4().hex}"
        _img_map[key] = (m.group(1), m.group(2))
        return f"\n\n{key}\n\n"  # isolated paragraph so it becomes its own section

    text = re.sub(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)", _extract_image, text)

    # ── Split on markdown tables ─────────────────────────────────────────────
    # Matches both pipe-surrounded (|col|col|) and bare (col | col) table styles.
    # Requires: header row with |, then a separator line (---|--- or |---|---|), then data rows.
    table_pattern = (
        r"((?:^|\n)"
        r"[^\n]*\|[^\n]*\n"  # header row — any line containing |
        r"[ \t]*\|?[ \t]*[-:]+[-| \t:]*\n"  # separator — ---|--- or |---|---|
        r"(?:[^\n]*\|[^\n]*\s*(?:\n|$))+"  # 1+ data rows
        r")"
    )
    parts = re.split(table_pattern, text, flags=re.MULTILINE)

    for part in parts:
        if not part.strip():
            continue

        # ── Is this chunk a table? ───────────────────────────────────────────
        lines = part.strip().split("\n")
        is_table = (
            len(lines) >= 3 and "|" in lines[0] and re.match(r"^[ \t]*\|?[ \t]*[-:]+[-| \t:]*$", lines[1].strip())
        )

        if is_table:
            table_blocks = convert_markdown_table_to_slack_blocks(part)
            blocks.extend(table_blocks)
            if table_blocks:
                blocks.append({"type": "divider"})
            continue

        # ── Non-table: replace HR markers, split into paragraphs ────────────
        # Match --- / *** / ___ on their own line, with or without surrounding blank lines
        part = re.sub(r"(?m)^[ \t]*([-*_]{3,})[ \t]*$", "<HR_DIVIDER>", part)
        sections = re.split(r"(?:\r\n|\n){2,}", part)

        for section in sections:
            stripped = section.strip()
            if not stripped:
                continue

            # Divider
            if stripped == "<HR_DIVIDER>":
                blocks.append({"type": "divider"})
                continue

            # ── Image sentinel ───────────────────────────────────────────────
            if stripped in _img_map:
                alt, url = _img_map[stripped]
                blocks.append(_image_block(alt, url))
                continue

            # ── Heading block (H1/H2 → header block; H3-H6 → bold text) ────
            heading_match = re.match(r"^\s*(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                # Strip any inline markdown from the heading text
                heading_text = re.sub(r"\*\*?([^*]+)\*\*?", r"\1", heading_text)
                # Auto-prepend a context emoji if the heading doesn't already have one
                heading_text = _auto_emoji_header(heading_text) + heading_text
                if level <= 2 and len(heading_text) <= 150:
                    # Add a visual section break before H1/H2 (skip if nothing above yet)
                    if blocks and blocks[-1].get("type") not in ("divider", "header"):
                        blocks.append({"type": "divider"})
                    blocks.append(
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": heading_text, "emoji": True},
                        }
                    )
                else:
                    blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*{heading_text}*"},
                        }
                    )
                continue

            # ── SQL / code block: auto-tag bare SQL so Slack renders it monospaced ──
            if stripped.startswith("```") or (not stripped.startswith("`") and _SQL_RE.match(stripped)):
                # Already fenced or looks like a bare SQL query — wrap in ```sql
                if stripped.startswith("```"):
                    formatted = stripped  # keep as-is
                else:
                    formatted = f"```sql\n{stripped}\n```"
                blocks.extend(_chunk_code_block(formatted))
                continue

            # ── Pure bullet list → native rich_text block ────────────────────
            sec_lines = [ln for ln in stripped.split("\n") if ln.strip()]
            if sec_lines and all(_BULLET_LINE_RE.match(ln.strip()) for ln in sec_lines):
                blocks.append(_to_rich_text_list(sec_lines, "bullet"))
                continue

            # ── Pure ordered list → native rich_text block ───────────────────
            if sec_lines and all(_ORDERED_LINE_RE.match(ln.strip()) for ln in sec_lines):
                blocks.append(_to_rich_text_list(sec_lines, "ordered"))
                continue

            # ── Mixed intro text + bullet list → section + rich_text ─────────
            # e.g. "Here are the findings:\n• Item 1\n• Item 2"
            if sec_lines:
                bullet_start = next((i for i, ln in enumerate(sec_lines) if _BULLET_LINE_RE.match(ln.strip())), None)
                if bullet_start and bullet_start > 0:
                    tail = sec_lines[bullet_start:]
                    if all(_BULLET_LINE_RE.match(ln.strip()) for ln in tail):
                        intro = format_text_for_slack("\n".join(sec_lines[:bullet_start]))
                        if intro.strip():
                            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": intro.strip()}})
                        blocks.append(_to_rich_text_list(tail, "bullet"))
                        continue

            # ── Regular text section ─────────────────────────────────────────
            formatted = format_text_for_slack(section)

            # Short footnote-style lines → context block (small grey text)
            if (
                len(formatted.strip()) < 200
                and "\n" not in formatted.strip()
                and any(formatted.strip().lower().startswith(p) for p in _CONTEXT_PREFIXES)
            ):
                blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": formatted.strip()}]})
                continue

            if len(formatted) > SLACK_MAX_TEXT_LENGTH:
                chunks = re.split(r"([.!?]\s+|\n)", formatted)
                current = ""
                for chunk in chunks:
                    if len(current) + len(chunk) > SLACK_MAX_TEXT_LENGTH:
                        if current:
                            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": current.strip()}})
                        current = chunk
                        while len(current) > SLACK_MAX_TEXT_LENGTH:
                            blocks.append(
                                {
                                    "type": "section",
                                    "text": {"type": "mrkdwn", "text": current[:SLACK_MAX_TEXT_LENGTH]},
                                }
                            )
                            current = current[SLACK_MAX_TEXT_LENGTH:]
                    else:
                        current += chunk
                if current:
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": current.strip()}})
            else:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": formatted}})

    # ── Deduplicate consecutive dividers ────────────────────────────────────
    deduped: list[dict] = []
    for block in blocks:
        if block.get("type") == "divider" and deduped and deduped[-1].get("type") == "divider":
            continue
        deduped.append(block)
    # Drop trailing divider — nothing useful follows
    if deduped and deduped[-1].get("type") == "divider":
        deduped.pop()

    return deduped


def chunk_blocks(
    blocks: list,
    max_blocks: int = SLACK_MAX_BLOCKS,
    max_chars: int = SLACK_MAX_TOTAL_PAYLOAD_CHARS,
) -> list:
    """Split a block list into chunks that fit within Slack's block-count limit
    AND a conservative total serialized-size budget (see SLACK_MAX_TOTAL_PAYLOAD_CHARS
    for why the size check is needed in addition to the count check)."""
    if len(blocks) <= max_blocks and len(json.dumps(blocks)) <= max_chars:
        return [blocks]

    chunks: list[list] = []
    current: list = []
    current_size = 2  # "[]"
    for block in blocks:
        block_size = len(json.dumps(block)) + 1  # +1 for separating comma
        if current and (len(current) >= max_blocks or current_size + block_size > max_chars):
            chunks.append(current)
            current = []
            current_size = 2
        current.append(block)
        current_size += block_size

    if current:
        chunks.append(current)

    return chunks
