//! Gameplay-focused loading and geometry for ai-delver levels.

use anyhow::{bail, Context, Result};
use serde::Deserialize;
use std::{
    fs,
    path::{Path, PathBuf},
};

pub const MAX_GRID_SIZE: usize = 100;
pub const DEFAULT_TILE_SIZE: f32 = 16.0;

/// The level data needed by gameplay and simulation code.
#[derive(Clone, Debug, PartialEq)]
pub struct Level {
    pub name: String,
    pub width: usize,
    pub height: usize,
    pub tile_size: f32,
    pub solid_tiles: Vec<(usize, usize)>,
    /// Bottom-left anchor of the Delver footprint.
    pub delver: (usize, usize),
    pub delver_size: (usize, usize),
    /// Bottom-left anchor of the Goal footprint.
    pub goal: (usize, usize),
    pub goal_size: (usize, usize),
}

#[derive(Deserialize)]
struct Root {
    #[serde(rename = "_name")]
    name: String,
    map: Map,
}

#[derive(Deserialize)]
struct Map {
    grid_size: [usize; 2],
    tile_size: [f32; 2],
    tilemap: Layers,
    world_objects_map: Layers,
}

#[derive(Deserialize)]
struct Layers {
    layers: Vec<Layer>,
}

#[derive(Deserialize)]
struct Layer {
    #[serde(default)]
    elements: Vec<Element>,
}

#[derive(Deserialize)]
struct Element {
    name: String,
    position: [usize; 2],
    #[serde(default = "default_size")]
    size: [usize; 2],
}

fn default_size() -> [usize; 2] {
    [1, 1]
}

impl Level {
    /// Loads and validates a level JSON file.
    pub fn load(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let text = fs::read_to_string(path)
            .with_context(|| format!("failed to read level {}", path.display()))?;
        Self::from_json(&text).with_context(|| format!("failed to load level {}", path.display()))
    }

    /// Parses and validates the serialized level schema.
    pub fn from_json(text: &str) -> Result<Self> {
        let root: Root = serde_json::from_str(text).context("invalid level JSON")?;
        let [width, height] = root.map.grid_size;
        let [tile_width, tile_height] = root.map.tile_size;

        if width == 0 || height == 0 || width > MAX_GRID_SIZE || height > MAX_GRID_SIZE {
            bail!("grid_size must be within 1..={MAX_GRID_SIZE}");
        }
        if !tile_width.is_finite()
            || !tile_height.is_finite()
            || tile_width <= 0.0
            || (tile_width - tile_height).abs() > f32::EPSILON
        {
            bail!("Rapier environment requires positive square tiles");
        }

        let mut solid_tiles = Vec::new();
        for element in root
            .map
            .tilemap
            .layers
            .iter()
            .flat_map(|layer| &layer.elements)
        {
            validate_position(element.position, width, height)?;
            if element.name == "platform" {
                solid_tiles.push((element.position[0], element.position[1]));
            }
        }

        let mut delvers = Vec::new();
        let mut goals = Vec::new();
        for element in root
            .map
            .world_objects_map
            .layers
            .iter()
            .flat_map(|layer| &layer.elements)
        {
            validate_position(element.position, width, height)?;
            let size = normalize_size(element.size)?;
            validate_footprint(element.position, size, width, height)?;
            match element.name.as_str() {
                "delver" => delvers.push((element.position[0], element.position[1], size)),
                "goal" => goals.push((element.position[0], element.position[1], size)),
                _ => {}
            }
        }

        if delvers.len() != 1 || goals.len() != 1 {
            bail!(
                "level must contain exactly one delver and one goal (found {}, {})",
                delvers.len(),
                goals.len()
            );
        }

        let (dx, dy, dsize) = delvers[0];
        let (gx, gy, gsize) = goals[0];

        Ok(Self {
            name: root.name,
            width,
            height,
            tile_size: tile_width,
            solid_tiles,
            delver: (dx, dy),
            delver_size: dsize,
            goal: (gx, gy),
            goal_size: gsize,
        })
    }

    /// Resolves either a direct path or a level-save name using `repo_root`.
    pub fn resolve(input: impl AsRef<Path>, repo_root: impl AsRef<Path>) -> Result<PathBuf> {
        let input = input.as_ref();
        let repo_root = repo_root.as_ref();
        let saves = repo_root.join("client/data/level_saves");
        let candidates = [
            input.to_path_buf(),
            input.join("level.json"),
            repo_root.join(input),
            repo_root.join(input).join("level.json"),
            saves.join(input),
            saves.join(input).join("level.json"),
        ];

        candidates
            .into_iter()
            .find(|path| path.is_file())
            .with_context(|| format!("could not resolve level '{}'", input.display()))
    }

    /// Returns the world-space center of a top-origin grid tile.
    pub fn tile_center(&self, tile: (usize, usize)) -> (f32, f32) {
        (
            (tile.0 as f32 + 0.5) * self.tile_size,
            (self.height as f32 - tile.1 as f32 - 0.5) * self.tile_size,
        )
    }

    /// Cells occupied by a bottom-left–anchored footprint (Y increases downward).
    pub fn footprint(position: (usize, usize), size: (usize, usize)) -> Vec<(usize, usize)> {
        let (x, y) = position;
        let (w, h) = size;
        let top_y = y + 1 - h;
        let mut cells = Vec::with_capacity(w * h);
        for dy in 0..h {
            for dx in 0..w {
                cells.push((x + dx, top_y + dy));
            }
        }
        cells
    }

    pub fn goal_tiles(&self) -> Vec<(usize, usize)> {
        Self::footprint(self.goal, self.goal_size)
    }

    /// World-space spawn for the Delver body center: horizontal center of the
    /// footprint, feet on the bottom of the standing (bottom-left) cell.
    pub fn delver_spawn_center(&self, player_height: f32) -> (f32, f32) {
        let (x, y) = self.delver;
        let (w, _) = self.delver_size;
        let cx = (x as f32 + w as f32 * 0.5) * self.tile_size;
        let cell_bottom = (self.height as f32 - y as f32 - 1.0) * self.tile_size;
        let cy = cell_bottom + player_height / 2.0;
        (cx, cy)
    }
}

fn normalize_size(size: [usize; 2]) -> Result<(usize, usize)> {
    let [w, h] = size;
    if w == 0 || h == 0 {
        bail!("element size must be at least [1, 1], got {size:?}");
    }
    Ok((w, h))
}

fn validate_position(position: [usize; 2], width: usize, height: usize) -> Result<()> {
    if position[0] >= width || position[1] >= height {
        bail!("element position {:?} is outside grid bounds", position);
    }
    Ok(())
}

fn validate_footprint(
    position: [usize; 2],
    size: (usize, usize),
    width: usize,
    height: usize,
) -> Result<()> {
    let (x, y) = (position[0], position[1]);
    let (w, h) = size;
    if y + 1 < h || x + w > width || y >= height {
        bail!(
            "element footprint at {:?} size {:?} is outside grid bounds {}x{}",
            position,
            size,
            width,
            height
        );
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    const VALID_LEVEL: &str = r#"{
        "_name":"test",
        "map":{
            "grid_size":[5,4],
            "tile_size":[16,16],
            "tilemap":{"layers":[
                {"elements":[{"name":"platform","position":[1,3]}]},
                {"elements":[{"name":"decoration","position":[2,2]}]}
            ]},
            "world_objects_map":{"layers":[{"elements":[
                {"name":"delver","position":[1,2]},
                {"name":"goal","position":[3,2]}
            ]}]}
        }
    }"#;

    #[test]
    fn parses_real_schema_and_computes_geometry() {
        let level = Level::from_json(VALID_LEVEL).unwrap();

        assert_eq!(level.name, "test");
        assert_eq!((level.width, level.height), (5, 4));
        assert_eq!(level.solid_tiles, vec![(1, 3)]);
        assert_eq!(level.delver, (1, 2));
        assert_eq!(level.delver_size, (1, 1));
        assert_eq!(level.goal, (3, 2));
        assert_eq!(level.goal_size, (1, 1));
        assert_eq!(level.tile_center(level.goal), (56.0, 24.0));
    }

    #[test]
    fn expands_multi_tile_footprints() {
        let json = r#"{
            "_name":"tall",
            "map":{
                "grid_size":[5,6],
                "tile_size":[16,16],
                "tilemap":{"layers":[{"elements":[]}]},
                "world_objects_map":{"layers":[{"elements":[
                    {"name":"delver","position":[1,4],"size":[1,3]},
                    {"name":"goal","position":[3,3],"size":[1,1]}
                ]}]}
            }
        }"#;
        let level = Level::from_json(json).unwrap();
        assert_eq!(level.delver_size, (1, 3));
        assert_eq!(
            Level::footprint(level.delver, level.delver_size),
            vec![(1, 2), (1, 3), (1, 4)]
        );
        let (sx, sy) = level.delver_spawn_center(38.0);
        assert!((sx - 24.0).abs() < 1e-3);
        // cell bottom of y=4 in height 6: (6-4-1)*16 = 16; + half height 19 = 35
        assert!((sy - 35.0).abs() < 1e-3);
    }

    #[test]
    fn rejects_invalid_grid_and_tile_geometry() {
        let oversized = VALID_LEVEL.replace("\"grid_size\":[5,4]", "\"grid_size\":[101,4]");
        assert!(Level::from_json(&oversized)
            .unwrap_err()
            .to_string()
            .contains("grid_size"));

        let rectangular = VALID_LEVEL.replace("\"tile_size\":[16,16]", "\"tile_size\":[16,8]");
        assert!(Level::from_json(&rectangular)
            .unwrap_err()
            .to_string()
            .contains("square tiles"));
    }

    #[test]
    fn rejects_out_of_bounds_elements() {
        let invalid = VALID_LEVEL.replace(
            r#"{"name":"decoration","position":[2,2]}"#,
            r#"{"name":"decoration","position":[5,2]}"#,
        );

        assert!(Level::from_json(&invalid)
            .unwrap_err()
            .to_string()
            .contains("outside grid bounds"));
    }

    #[test]
    fn requires_exactly_one_delver_and_goal() {
        let no_goal = VALID_LEVEL.replace(
            r#"{"name":"goal","position":[3,2]}"#,
            r#"{"name":"npc","position":[3,2]}"#,
        );
        assert!(Level::from_json(&no_goal)
            .unwrap_err()
            .to_string()
            .contains("found 1, 0"));

        let duplicate_delver = VALID_LEVEL.replace(
            r#"{"name":"delver","position":[1,2]}"#,
            r#"{"name":"delver","position":[1,2]},{"name":"delver","position":[2,2]}"#,
        );
        assert!(Level::from_json(&duplicate_delver)
            .unwrap_err()
            .to_string()
            .contains("found 2, 1"));
    }

    #[test]
    fn resolves_named_level_directory_and_loads_it() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root =
            std::env::temp_dir().join(format!("ai-delver-level-{}-{nonce}", std::process::id()));
        let level_dir = root.join("client/data/level_saves/example");
        fs::create_dir_all(&level_dir).unwrap();
        let level_path = level_dir.join("level.json");
        fs::write(&level_path, VALID_LEVEL).unwrap();

        assert_eq!(Level::resolve("example", &root).unwrap(), level_path);
        assert_eq!(Level::load(&level_path).unwrap().name, "test");

        fs::remove_dir_all(root).unwrap();
    }
}
