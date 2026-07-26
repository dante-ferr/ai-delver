#[derive(Clone)]
pub struct ExplorationGrid {
    width: usize,
    height: usize,
    visited: Vec<bool>,
}

impl ExplorationGrid {
    pub fn new(width: usize, height: usize) -> Self {
        Self {
            width,
            height,
            visited: vec![false; width * height],
        }
    }

    /// Circular footprint used by unit tests; production uses [`Self::step_on_vertical_span`].
    #[cfg(test)]
    pub fn step_on(&mut self, x: i32, y: i32, radius: i32) -> bool {
        if x < 0 || y < 0 || x >= self.width as i32 || y >= self.height as i32 {
            return false;
        }
        let was_new = !self.visited[y as usize * self.width + x as usize];
        for yy in (y - radius).max(0)..=(y + radius).min(self.height as i32 - 1) {
            for xx in (x - radius).max(0)..=(x + radius).min(self.width as i32 - 1) {
                if (xx - x).pow(2) + (yy - y).pow(2) <= radius.pow(2) {
                    self.visited[yy as usize * self.width + xx as usize] = true;
                }
            }
        }
        was_new
    }

    /// Sweeps a vertical span (from feet_y to head_y) at horizontal position x,
    /// painting `x±radius_x` × body height. Returns how many cells flipped
    /// unvisited → visited (air and floor). Used for per-tile exploration pay.
    pub fn step_on_vertical_span(
        &mut self,
        x: i32,
        feet_y: i32,
        head_y: i32,
        radius_x: i32,
    ) -> usize {
        if x < 0 || feet_y >= self.height as i32 || head_y < 0 || x >= self.width as i32 {
            return 0;
        }
        let (min_y, max_y) = (feet_y.min(head_y), feet_y.max(head_y));
        let start_x = (x - radius_x).max(0);
        let end_x = (x + radius_x).min(self.width as i32 - 1);
        let start_y = min_y.max(0);
        let end_y = max_y.min(self.height as i32 - 1);

        let mut newly_marked = 0usize;
        for yy in start_y..=end_y {
            for xx in start_x..=end_x {
                let idx = yy as usize * self.width + xx as usize;
                if !self.visited[idx] {
                    self.visited[idx] = true;
                    newly_marked += 1;
                }
            }
        }
        newly_marked
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn circular_radius_does_not_mark_corners() {
        let mut grid = ExplorationGrid::new(5, 5);
        assert!(grid.step_on(2, 2, 1));
        assert!(!grid.step_on(2, 1, 0));
        assert!(grid.step_on(1, 1, 0));
    }

    #[test]
    fn vertical_span_counts_new_tiles_once() {
        let mut grid = ExplorationGrid::new(10, 10);
        // Grounded brush at x=2, feet=4, head=2, radius_x=0 → 3 cells
        assert_eq!(grid.step_on_vertical_span(2, 4, 2, 0), 3);
        // Same footprint again → 0
        assert_eq!(grid.step_on_vertical_span(2, 4, 2, 0), 0);
        // Jump higher (head=0) marks two new apex rows
        assert_eq!(grid.step_on_vertical_span(2, 4, 0, 0), 2);
    }

    #[test]
    fn radius_x_marks_side_columns() {
        let mut grid = ExplorationGrid::new(10, 10);
        // radius_x=1, 3 rows → 3×3 = 9
        assert_eq!(grid.step_on_vertical_span(2, 4, 2, 1), 9);
        assert_eq!(grid.step_on_vertical_span(2, 4, 2, 1), 0);
    }
}
