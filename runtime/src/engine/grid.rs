/// A 2-D tile grid that owns the level layout.
///
/// Tile values:
///   0 = empty
///   1 = solid platform
///   3 = goal
pub struct TileGrid {
    pub width: usize,
    pub height: usize,
    pub tile_size: f32,
    cells: Vec<Vec<u8>>,
}

impl TileGrid {
    pub fn new(width: usize, height: usize, tile_size: f32) -> Self {
        TileGrid {
            width,
            height,
            tile_size,
            cells: vec![vec![0u8; width]; height],
        }
    }

    pub fn set(&mut self, x: usize, y: usize, value: u8) {
        if x < self.width && y < self.height {
            self.cells[y][x] = value;
        }
    }

    /// Returns the tile value at (x, y). Returns 0 for out-of-bounds coordinates.
    pub fn get(&self, x: i32, y: i32) -> u8 {
        if x < 0 || y < 0 || x >= self.width as i32 || y >= self.height as i32 {
            return 0;
        }
        self.cells[y as usize][x as usize]
    }

    /// Returns the tile coordinate ranges that overlap the given AABB (in pixel space).
    /// All returned indices are guaranteed to be valid for this grid.
    pub fn tile_coords_for_aabb(
        &self,
        left: f32,
        right: f32,
        bottom: f32,
        top: f32,
    ) -> (usize, usize, usize, usize) {
        let w = self.width as i32 - 1;
        let h = self.height as i32 - 1;
        let map_height_px = self.height as f32 * self.tile_size;

        let min_tx = ((left / self.tile_size).floor() as i32).clamp(0, w) as usize;
        let max_tx = ((right / self.tile_size).floor() as i32).clamp(0, w) as usize;
        // Y-axis is flipped: tile row 0 is the top of the map in pixel space.
        let min_ty = (((map_height_px - top) / self.tile_size).floor() as i32).clamp(0, h) as usize;
        let max_ty =
            (((map_height_px - bottom) / self.tile_size).floor() as i32).clamp(0, h) as usize;

        (min_tx, max_tx, min_ty, max_ty)
    }
}
