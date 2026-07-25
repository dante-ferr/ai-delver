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

    /// Sweeps a vertical span (from feet_y to head_y) at horizontal position x.
    /// Marks all tiles along the vertical body height as visited.
    /// Returns true if any tile in the center span was previously unvisited.
    pub fn step_on_vertical_span(
        &mut self,
        x: i32,
        feet_y: i32,
        head_y: i32,
        radius_x: i32,
    ) -> bool {
        if x < 0 || feet_y >= self.height as i32 || head_y < 0 || x >= self.width as i32 {
            return false;
        }
        let (min_y, max_y) = (feet_y.min(head_y), feet_y.max(head_y));
        let mut was_new = false;

        for y in min_y.max(0)..=max_y.min(self.height as i32 - 1) {
            let idx = y as usize * self.width + x as usize;
            if !self.visited[idx] {
                was_new = true;
            }
        }

        let start_x = (x - radius_x).max(0);
        let end_x = (x + radius_x).min(self.width as i32 - 1);
        let start_y = min_y.max(0);
        let end_y = max_y.min(self.height as i32 - 1);

        for yy in start_y..=end_y {
            for xx in start_x..=end_x {
                self.visited[yy as usize * self.width + xx as usize] = true;
            }
        }

        was_new
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
    fn vertical_span_prevents_duplicate_air_jump_exploration() {
        let mut grid = ExplorationGrid::new(10, 10);
        // Delver walks on ground at x=2, feet_y=4, head_y=2 (3 tiles tall: rows 2, 3, 4)
        assert!(grid.step_on_vertical_span(2, 4, 2, 0));

        // Delver subsequently jumps into the air at x=2, feet_y=2, head_y=0 (rows 0, 1, 2)
        // Since rows 2, 3, 4 were already marked visited during ground walk, stepping at row 2 returns false for new exploration
        assert!(!grid.step_on_vertical_span(2, 4, 2, 0));
    }
}

