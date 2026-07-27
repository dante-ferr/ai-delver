"""Build tuned TrueType copies (vertical stretch + tighter tracking)."""

from __future__ import annotations

from pathlib import Path

from fontTools.misc.transform import Identity
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


def transform_font(
    src: Path,
    dest: Path,
    *,
    y_scale: float = 1.0,
    tracking: float = 1.0,
) -> None:
    """Rewrite ``src`` into ``dest`` with optional Y stretch and advance tightening.

    ``tracking`` < 1.0 shortens glyph advances (tighter letter spacing) without
    scaling outlines. Side bearings shrink evenly so shapes stay centered.
    """
    y_scale = float(y_scale)
    tracking = float(tracking)
    if abs(y_scale - 1.0) < 1e-6 and abs(tracking - 1.0) < 1e-6:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        return

    font = TTFont(str(src))

    if abs(y_scale - 1.0) >= 1e-6:
        if "glyf" not in font:
            raise ValueError(f"{src.name} has no glyf table; cannot vertical-scale")
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
        for attr in (
            "sTypoAscender",
            "sTypoDescender",
            "sTypoLineGap",
            "sxHeight",
            "sCapHeight",
        ):
            if hasattr(os2, attr):
                setattr(os2, attr, _scale_int(getattr(os2, attr), y_scale))
        for attr in ("usWinAscent", "usWinDescent"):
            if hasattr(os2, attr):
                setattr(os2, attr, abs(_scale_int(getattr(os2, attr), y_scale)))

        head = font["head"]
        head.yMin = _scale_int(head.yMin, y_scale)
        head.yMax = _scale_int(head.yMax, y_scale)

    if abs(tracking - 1.0) >= 1e-6 and "hmtx" in font:
        hmtx = font["hmtx"].metrics
        for name, (width, lsb) in list(hmtx.items()):
            new_width = max(0, _scale_int(width, tracking))
            shrink = width - new_width
            new_lsb = lsb - shrink // 2
            hmtx[name] = (new_width, new_lsb)

    dest.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(dest))


# Back-compat alias used by older call sites / docs.
def scale_font_vertically(src: Path, dest: Path, y_scale: float) -> None:
    transform_font(src, dest, y_scale=y_scale, tracking=1.0)


def _scale_int(value: int, scale: float) -> int:
    return int(round(value * scale))
