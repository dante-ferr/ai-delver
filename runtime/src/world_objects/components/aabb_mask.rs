use crate::engine::grid::TileGrid;

/// Axis-aligned mask attached to an entity body center.
///
/// Defined by absolute `width` / `height` plus optional center offsets from the body.
/// Physics and hazard masks share this same shape.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct AabbMask {
    pub width: f32,
    pub height: f32,
    pub offset_x: f32,
    pub offset_y: f32,
}

impl AabbMask {
    /// Body-centered mask (`offset_x` / `offset_y` = 0).
    pub fn new(width: f32, height: f32) -> Self {
        Self::with_offsets(width, height, 0.0, 0.0)
    }

    /// Absolute size with center offsets from the body (same construction for every mask).
    pub fn with_offsets(width: f32, height: f32, offset_x: f32, offset_y: f32) -> Self {
        Self {
            width,
            height,
            offset_x,
            offset_y,
        }
    }

    pub fn bounds(&self, body_x: f32, body_y: f32) -> AabbBounds {
        let cx = body_x + self.offset_x;
        let cy = body_y + self.offset_y;
        let half_w = self.width * 0.5;
        let half_h = self.height * 0.5;
        AabbBounds {
            left: cx - half_w,
            right: cx + half_w,
            bottom: cy - half_h,
            top: cy + half_h,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct AabbBounds {
    pub left: f32,
    pub right: f32,
    pub bottom: f32,
    pub top: f32,
}

impl AabbBounds {
    /// True if any grid cell overlapping this AABB holds `tile`.
    pub fn overlaps_tile(&self, grid: &TileGrid, tile: u8) -> bool {
        let (min_tx, max_tx, min_ty, max_ty) =
            grid.tile_coords_for_aabb(self.left, self.right, self.bottom, self.top);
        for ty in min_ty..=max_ty {
            for tx in min_tx..=max_tx {
                if grid.get(tx as i32, ty as i32) == tile {
                    return true;
                }
            }
        }
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn offset_mask_matches_width_height_offset_y() {
        let mask = AabbMask::with_offsets(10.0, 18.0, 0.0, 9.0);
        assert_eq!(mask.width, 10.0);
        assert_eq!(mask.height, 18.0);
        assert_eq!(mask.offset_y, 9.0);

        let b = mask.bounds(100.0, 50.0);
        assert_eq!(b.left, 95.0);
        assert_eq!(b.right, 105.0);
        assert_eq!(b.bottom, 50.0);
        assert_eq!(b.top, 68.0);
    }

    #[test]
    fn body_centered_mask() {
        let mask = AabbMask::new(10.0, 38.0);
        let b = mask.bounds(0.0, 0.0);
        assert_eq!(b.left, -5.0);
        assert_eq!(b.right, 5.0);
        assert_eq!(b.bottom, -19.0);
        assert_eq!(b.top, 19.0);
    }
}
