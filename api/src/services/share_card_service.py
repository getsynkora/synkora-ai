"""
Render branded shareable scorecards for shared conversations.
"""

from __future__ import annotations

import math
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_SYSTEM_FONT_DIR = Path("/System/Library/Fonts/Supplemental")

_BOLD_CANDIDATES = [
    _FONT_DIR / "Geist-Bold.ttf",
    _SYSTEM_FONT_DIR / "Arial Bold.ttf",
    _FONT_DIR / "Geist-Regular.ttf",
]
_DISPLAY_CANDIDATES = [
    _FONT_DIR / "DINCondensedBold.ttf",
    _SYSTEM_FONT_DIR / "DIN Condensed Bold.ttf",
    _FONT_DIR / "Geist-Bold.ttf",
    _SYSTEM_FONT_DIR / "Arial Bold.ttf",
    _FONT_DIR / "Geist-Regular.ttf",
]
_REGULAR_CANDIDATES = [
    _FONT_DIR / "Geist-Regular.ttf",
]


def _load_font(size: int, candidates: list[Path] | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates or _REGULAR_CANDIDATES:
        try:
            return ImageFont.truetype(str(path), size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _load_bold(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return _load_font(size, _BOLD_CANDIDATES)


def _load_display(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return _load_font(size, _DISPLAY_CANDIDATES)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, max_length: int) -> str:
    value = _normalize_text(value)
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "…"


def _extract_classification(content: str) -> str | None:
    lowered = content.lower()
    if "growth mindset" in lowered:
        return "Growth mindset"
    if "mixed mindset" in lowered:
        return "Mixed mindset"
    if "fixed mindset" in lowered:
        return "Fixed mindset"
    return None


def _extract_score_percent(content: str) -> int | None:
    percent_match = re.search(r"(\d{1,3})\s*(?:%|/\s*100)", content, re.IGNORECASE)
    if percent_match:
        return max(0, min(100, int(percent_match.group(1))))

    fraction_match = re.search(r"overall score[^0-9]*([01](?:\.\d+)?)\s*/\s*1(?:\.00)?", content, re.IGNORECASE)
    if fraction_match:
        return max(0, min(100, round(float(fraction_match.group(1)) * 100)))

    return None


def _extract_section_bullets(content: str, heading_pattern: str) -> list[str]:
    section_match = re.search(
        rf"{heading_pattern}(.*?)(?:\n\s*---|\n\s*###|\n\s*##|\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        return []

    bullets = []
    for line in section_match.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        cleaned = stripped.lstrip("-").strip()
        if "—" in cleaned:
            cleaned = cleaned.split("—", 1)[1].strip()
        cleaned = re.sub(r"\*+", "", cleaned).strip()
        if cleaned:
            bullets.append(_truncate(cleaned, 90))

    return bullets


def _infer_domain(conversation_name: str | None, agent_name: str | None, messages: list[dict[str, Any]]) -> str:
    sample = " ".join(
        filter(
            None,
            [
                conversation_name or "",
                agent_name or "",
                *[str(message.get("content", "")) for message in messages[-4:]],
            ],
        )
    ).lower()

    if any(word in sample for word in ["coding", "code", "developer", "programming", "software", "engineering"]):
        return "Coding"
    if any(word in sample for word in ["leadership", "manager", "team", "management"]):
        return "Leadership"
    if any(word in sample for word in ["career", "job", "work", "promotion"]):
        return "Career"
    return "Mindset"


def extract_share_card_data(
    conversation_name: str | None,
    agent_name: str | None,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    assistant_messages = [m for m in messages if str(m.get("role", "")).upper() == "ASSISTANT"]
    last_message = assistant_messages[-1] if assistant_messages else {}
    content = str(last_message.get("content", "") or "")
    metadata = last_message.get("metadata") or {}
    result = metadata.get("mindset_result") if isinstance(metadata, dict) else None

    classification = None
    score_percent = None
    headline = None
    insight = None
    strengths: list[str] = []
    growth_edges: list[str] = []
    domain = None

    if isinstance(result, dict):
        classification = result.get("classification")
        score_raw = result.get("score_percent", result.get("score"))
        if isinstance(score_raw, (int, float)):
            score_percent = round(score_raw * 100) if score_raw <= 1 else round(score_raw)
        elif isinstance(score_raw, str):
            score_percent = _extract_score_percent(score_raw)
        headline = result.get("headline")
        insight = result.get("insight")
        strengths = [str(item) for item in result.get("strengths", [])[:2]]
        growth_edges = [str(item) for item in result.get("growth_edges", [])[:2]]
        domain = result.get("domain")

    classification = classification or _extract_classification(content) or "Mixed mindset"
    score_percent = score_percent if score_percent is not None else _extract_score_percent(content) or 44
    strengths = strengths or _extract_section_bullets(content, r"Strongest Growth-Pattern Signals")
    growth_edges = growth_edges or _extract_section_bullets(content, r"Strongest Fixed-Pattern Signals")
    domain = domain or _infer_domain(conversation_name, agent_name, messages)

    tone = "mixed"
    lowered_classification = classification.lower()
    if "growth" in lowered_classification:
        tone = "growth"
    elif "fixed" in lowered_classification:
        tone = "fixed"

    if not headline:
        if tone == "growth":
            headline = f"Growth is already your default in {domain.lower()}."
        elif tone == "fixed":
            headline = f"Your default in {domain.lower()} is protection before progress."
        else:
            headline = f"You are closer to growth than you think in {domain.lower()}."

    if not insight:
        if tone == "growth":
            insight = (
                f"You already treat challenge in {domain.lower()} as something that can be built through practice."
            )
        elif tone == "fixed":
            insight = f"Right now, pressure in {domain.lower()} makes self-protection louder than learning."
        else:
            insight = (
                f"Pressure can still pull you back toward comfort, certainty, or self-protection in {domain.lower()}."
            )

    if not strengths:
        strengths = ["Belief that practice, feedback, and persistence can improve capability."]
    if not growth_edges:
        growth_edges = ["Recover with a better strategy after setbacks."]

    return {
        "classification": _truncate(classification, 32),
        "score_percent": max(0, min(100, int(score_percent))),
        "headline": _truncate(headline, 112),
        "insight": _truncate(insight, 220),
        "strength": _truncate(strengths[0], 168),
        "growth_edge": _truncate(growth_edges[0], 168),
        "domain": _truncate(domain, 24),
        "tone": tone,
    }


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _wrap_text_clamped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
        else:
            current = candidate

    if len(lines) < max_lines and current:
        lines.append(current)

    consumed = " ".join(lines).split()
    if len(consumed) >= len(words):
        return lines[:max_lines]

    if not lines:
        return []

    last = lines[max_lines - 1] if len(lines) >= max_lines else lines[-1]
    while last and draw.textlength(f"{last}…", font=font) > max_width:
        last = last[:-1].rstrip()
    replacement = f"{last.rstrip(' ,.-')}…" if last else "…"
    if len(lines) >= max_lines:
        lines[max_lines - 1] = replacement
    else:
        lines[-1] = replacement
    return lines[:max_lines]


def _draw_gradient_rect(
    image: Image.Image,
    box: tuple[int, int, int, int],
    color_a: tuple[int, int, int],
    color_b: tuple[int, int, int],
    radius: int = 0,
    alpha: int = 255,
) -> None:
    """Draw a vertical gradient rectangle onto image."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for row in range(h):
        t = row / max(1, h - 1)
        r = int(color_a[0] + (color_b[0] - color_a[0]) * t)
        g = int(color_a[1] + (color_b[1] - color_a[1]) * t)
        b = int(color_a[2] + (color_b[2] - color_a[2]) * t)
        ImageDraw.Draw(layer).line([(0, row), (w - 1, row)], fill=(r, g, b, alpha))
    if radius:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
        layer.putalpha(mask)
    image.alpha_composite(layer, (x0, y0))


def _draw_shadow(
    image: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
    *,
    blur: int = 22,
    offset: tuple[int, int] = (0, 10),
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    ox, oy = offset
    layer_draw.rounded_rectangle((x0 + ox, y0 + oy, x1 + ox, y1 + oy), radius=radius, fill=fill)
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def render_share_card_png(card: dict[str, Any]) -> bytes:
    W, H = 1200, 630

    brand_pink = (255, 91, 143)
    brand_pink_deep = (237, 63, 122)
    brand_mint = (102, 224, 197)
    brand_mint_deep = (58, 188, 160)
    soft = (255, 231, 238)
    soft_alt = (220, 248, 240)

    if card["tone"] == "growth":
        primary = brand_mint
        secondary = brand_mint_deep
    elif card["tone"] == "fixed":
        primary = brand_pink
        secondary = brand_pink_deep
    else:
        primary = brand_pink
        secondary = brand_mint

    image = Image.new("RGBA", (W, H), (250, 247, 241, 255))
    draw = ImageDraw.Draw(image)

    for y in range(H):
        t = y / (H - 1)
        r = int(249 + (255 - 249) * t)
        g = int(245 + (255 - 245) * t)
        b = int(238 + (255 - 238) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-120, -80, 440, 320), fill=(*soft, 120))
    glow_draw.ellipse((820, -70, 1260, 260), fill=(*soft_alt, 140))
    glow_draw.ellipse((260, 430, 730, 820), fill=(255, 244, 214, 90))
    glow_draw.ellipse((880, 500, 1260, 760), fill=(*brand_mint, 36))
    image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))

    panel = (38, 24, 1162, 604)
    _draw_shadow(image, panel, 32, (188, 170, 138, 58), blur=26, offset=(0, 12))
    draw.rounded_rectangle(panel, radius=32, fill=(255, 255, 255, 244), outline=(229, 224, 214, 255), width=2)

    f_kicker = _load_font(14)
    f_label = _load_font(13)
    f_title = _load_bold(38)
    f_headline = _load_bold(28)
    f_body = _load_font(18)
    f_card_body = _load_font(16)
    f_score = _load_display(124)
    f_score_suffix = _load_display(34)
    f_footer = _load_font(13)

    left = 88
    right = 1110
    top = 62

    draw.text((left, top), "SYNKORA AI", font=f_kicker, fill=(92, 95, 112, 205))
    draw.text((left, top + 21), "MINDSET SCORECARD", font=f_kicker, fill=(129, 133, 150, 190))

    domain_text = card["domain"].upper()
    domain_w = int(draw.textlength(domain_text, font=f_label))
    domain_box = (right - domain_w - 26, top - 2, right, top + 26)
    draw.rounded_rectangle(domain_box, radius=16, fill=(*soft, 255), outline=(*primary, 46), width=1)
    draw.text((domain_box[0] + 13, domain_box[1] + 7), domain_text, font=f_label, fill=(*primary, 235))

    divider_y = top + 40
    draw.line([(left - 6, divider_y), (right, divider_y)], fill=(225, 227, 232, 255), width=2)

    score_x = left
    score_y = 146
    draw.text((score_x, score_y - 24), "YOUR MINDSET SCORE", font=f_label, fill=(153, 162, 176, 255))
    draw.text((score_x, score_y), str(card["score_percent"]), font=f_score, fill=(*primary, 255))
    score_box = draw.textbbox((score_x, score_y), str(card["score_percent"]), font=f_score)
    draw.text((score_box[2] + 10, score_y + 78), "/100", font=f_score_suffix, fill=(202, 207, 218, 255))

    classification_color = primary
    draw.text((score_x, score_box[3] + 8), card["classification"], font=f_title, fill=(*classification_color, 240))

    summary = (
        f"Research-based read on how you respond to setbacks, feedback, and difficulty in {card['domain'].lower()}."
    )
    summary_lines = _wrap_text_clamped(draw, summary, f_body, 430, 2)
    text_y = score_box[3] + 58
    for line in summary_lines:
        draw.text((score_x, text_y), line, font=f_body, fill=(101, 109, 126, 235))
        text_y += 25

    gauge_cx = 880
    gauge_cy = 224
    gauge_r = 124
    gauge_box = (gauge_cx - gauge_r, gauge_cy - gauge_r, gauge_cx + gauge_r, gauge_cy + gauge_r)
    _draw_shadow(
        image,
        (gauge_box[0] - 16, gauge_box[1] - 16, gauge_box[2] + 16, gauge_box[3] + 16),
        999,
        (206, 196, 173, 48),
        blur=24,
        offset=(0, 10),
    )
    draw.ellipse(
        (gauge_box[0] - 14, gauge_box[1] - 14, gauge_box[2] + 14, gauge_box[3] + 14),
        fill=(252, 251, 248, 255),
        outline=(230, 226, 216, 255),
        width=2,
    )
    draw.arc(gauge_box, start=150, end=228, fill=(*soft, 255), width=18)
    draw.arc(gauge_box, start=231, end=309, fill=(241, 238, 232, 255), width=18)
    draw.arc(gauge_box, start=312, end=390, fill=(*soft_alt, 255), width=18)
    progress_end = 150 + 240 * (card["score_percent"] / 100)
    draw.arc(gauge_box, start=150, end=progress_end, fill=(*brand_pink, 255), width=18)

    for tick in range(0, 101, 20):
        angle = math.radians(150 + 240 * (tick / 100))
        inner = gauge_r - 16
        outer = gauge_r + 2
        x0 = gauge_cx + inner * math.cos(angle)
        y0 = gauge_cy + inner * math.sin(angle)
        x1 = gauge_cx + outer * math.cos(angle)
        y1 = gauge_cy + outer * math.sin(angle)
        draw.line([(x0, y0), (x1, y1)], fill=(198, 203, 214, 255), width=2)

    marker_angle = math.radians(progress_end)
    mx = gauge_cx + gauge_r * math.cos(marker_angle)
    my = gauge_cy + gauge_r * math.sin(marker_angle)
    draw.ellipse((mx - 9, my - 9, mx + 9, my + 9), fill=(255, 255, 255, 255), outline=(*brand_pink, 255), width=4)

    center_score = f"{card['score_percent']}%"
    center_score_box = draw.textbbox((0, 0), center_score, font=f_title)
    draw.text(
        (gauge_cx - (center_score_box[2] - center_score_box[0]) / 2, gauge_cy - 34),
        center_score,
        font=f_title,
        fill=(33, 37, 45, 255),
    )
    center_class = card["classification"].replace(" mindset", "")
    center_class_box = draw.textbbox((0, 0), center_class, font=f_body)
    draw.text(
        (gauge_cx - (center_class_box[2] - center_class_box[0]) / 2, gauge_cy + 2),
        center_class,
        font=f_body,
        fill=(113, 121, 139, 255),
    )
    draw.text((gauge_cx - 146, gauge_cy + 108), "FIXED", font=f_label, fill=(*brand_pink_deep, 210))
    draw.text((gauge_cx - 24, gauge_cy - 142), "MIXED", font=f_label, fill=(132, 126, 117, 210))
    draw.text((gauge_cx + 98, gauge_cy + 108), "GROWTH", font=f_label, fill=(*brand_mint_deep, 210))

    headline_y = 390
    draw.text((left, headline_y), "ASSESSMENT SUMMARY", font=f_label, fill=(153, 162, 176, 255))
    headline_lines = _wrap_text_clamped(draw, card["headline"], f_headline, right - left, 2)
    text_y = headline_y + 18
    for line in headline_lines:
        draw.text((left, text_y), line, font=f_headline, fill=(28, 32, 40, 255))
        text_y += 32

    insight_lines = _wrap_text_clamped(draw, card["insight"], f_body, right - left, 2)
    for line in insight_lines:
        draw.text((left, text_y + 4), line, font=f_body, fill=(101, 109, 126, 238))
        text_y += 24

    card_y = 472
    card_h = 96
    gap = 18
    card_w = (right - left - gap) // 2
    card_boxes = [
        (
            (left, card_y, left + card_w, card_y + card_h),
            "STRONGEST SIGNAL",
            "What is already working",
            card["strength"],
        ),
        (
            (left + card_w + gap, card_y, right, card_y + card_h),
            "NEXT GROWTH EDGE",
            "Where to lean next",
            card["growth_edge"],
        ),
    ]

    for box, title, badge_text, body in card_boxes:
        _draw_shadow(image, box, 24, (196, 182, 153, 34), blur=18, offset=(0, 8))
        draw.rounded_rectangle(box, radius=24, fill=(251, 247, 239, 255), outline=(229, 220, 205, 255), width=2)
        badge_w = int(draw.textlength(badge_text, font=f_label)) + 24
        badge_box = (box[2] - badge_w - 18, box[1] + 16, box[2] - 18, box[1] + 42)
        draw.rounded_rectangle(badge_box, radius=14, fill=(*soft, 255), outline=(*primary, 34), width=1)
        draw.text((badge_box[0] + 12, badge_box[1] + 7), badge_text, font=f_label, fill=(*primary, 220))
        draw.text((box[0] + 22, box[1] + 18), title, font=f_label, fill=(143, 132, 112, 255))

        quote_lines = _wrap_text_clamped(draw, body, f_card_body, box[2] - box[0] - 44, 3)
        quote_y = box[1] + 46
        for line in quote_lines:
            draw.text((box[0] + 22, quote_y), line, font=f_card_body, fill=(84, 82, 79, 250))
            quote_y += 20

    footer_y = 576
    draw.line([(left, footer_y), (left + 208, footer_y)], fill=(*brand_pink, 180), width=2)
    draw.line([(left + 208, footer_y), (right, footer_y)], fill=(*brand_mint, 170), width=2)
    draw.ellipse((left, footer_y + 10, left + 8, footer_y + 18), fill=(*brand_pink, 220))
    draw.ellipse((left + 12, footer_y + 10, left + 20, footer_y + 18), fill=(255, 192, 214, 220))
    draw.ellipse((left + 24, footer_y + 10, left + 32, footer_y + 18), fill=(*brand_mint, 220))
    draw.text((left + 42, footer_y + 8), "Shareable result by Synkora AI", font=f_footer, fill=(150, 154, 164, 255))
    draw.text((right, footer_y + 8), "Synkora AI", font=f_footer, fill=(150, 154, 164, 255), anchor="ra")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
