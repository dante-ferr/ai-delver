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
}
