"""Build a vertically stretched copy of a TrueType font (taller glyphs, same width)."""

from __future__ import annotations

from pathlib import Path

from fontTools.misc.transform import Identity
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


def scale_font_vertically(src: Path, dest: Path, y_scale: float) -> None:
    """Scale glyph Y (and vertical metrics) by ``y_scale``; leave advances alone."""
    if abs(y_scale - 1.0) < 1e-6:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        return

    font = TTFont(str(src))
    glyph_set = font.getGlyphSet()
    glyf_table = font["glyf"]
    transform = Identity.scale(1.0, y_scale)

    for name in list(glyph_set.keys()):
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(TransformPen(pen, transform))
        glyf_table[name] = pen.glyph()

    hhea = font["hhea"]
    hhea.ascent = _scale_int(hhea.ascent, y_scale)
    hhea.descent = _scale_int(hhea.descent, y_scale)
    hhea.lineGap = _scale_int(hhea.lineGap, y_scale)

    os2 = font["OS/2"]
    # Signed typographic metrics
    for attr in ("sTypoAscender", "sTypoDescender", "sTypoLineGap", "sxHeight", "sCapHeight"):
        if hasattr(os2, attr):
            setattr(os2, attr, _scale_int(getattr(os2, attr), y_scale))
    # Unsigned Windows clip metrics
    for attr in ("usWinAscent", "usWinDescent"):
        if hasattr(os2, attr):
            setattr(os2, attr, abs(_scale_int(getattr(os2, attr), y_scale)))

    head = font["head"]
    head.yMin = _scale_int(head.yMin, y_scale)
    head.yMax = _scale_int(head.yMax, y_scale)

    dest.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(dest))


def _scale_int(value: int, y_scale: float) -> int:
    return int(round(value * y_scale))
