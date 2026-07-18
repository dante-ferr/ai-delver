import math


def brush_cells(
    continuous_pos: tuple[float, float], size: int
) -> list[tuple[int, int]]:
    """Return the square brush cells for a continuous grid position.

    Odd sizes center on the tile under the cursor. Even sizes pivot on the
    nearest tile crossing (vertex), so the brush only moves when the cursor
    gets closer to another crossing.
    """
    if size < 1:
        raise ValueError(f"Brush size must be at least 1, got {size}.")

    px, py = brush_pivot(continuous_pos, size)
    half = size // 2
    return [
        (px - half + dx, py - half + dy)
        for dy in range(size)
        for dx in range(size)
    ]


def brush_bottom_left(
    continuous_pos: tuple[float, float], size: int
) -> tuple[int, int]:
    """Bottom-left cell of the brush square (for outline / footprint helpers)."""
    if size < 1:
        raise ValueError(f"Brush size must be at least 1, got {size}.")

    cells = brush_cells(continuous_pos, size)
    min_x = min(x for x, _ in cells)
    max_y = max(y for _, y in cells)
    return (min_x, max_y)


def brush_pivot(
    continuous_pos: tuple[float, float], size: int
) -> tuple[int, int]:
    """Stable pivot identity for redraw / stroke dedupe.

    Odd sizes: the tile under the cursor. Even sizes: the nearest crossing.
    """
    if size < 1:
        raise ValueError(f"Brush size must be at least 1, got {size}.")

    gx, gy = continuous_pos
    if size % 2 == 1:
        return (math.floor(gx), math.floor(gy))
    return (math.floor(gx + 0.5), math.floor(gy + 0.5))
