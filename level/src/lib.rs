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
    pub delver: (usize, usize),
    pub goal: (usize, usize),
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
            match element.name.as_str() {
                "delver" => delvers.push((element.position[0], element.position[1])),
                "goal" => goals.push((element.position[0], element.position[1])),
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

        Ok(Self {
            name: root.name,
            width,
            height,
            tile_size: tile_width,
            solid_tiles,
            delver: delvers[0],
            goal: goals[0],
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
}

fn validate_position(position: [usize; 2], width: usize, height: usize) -> Result<()> {
    if position[0] >= width || position[1] >= height {
        bail!("element position {:?} is outside grid bounds", position);
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
        assert_eq!(level.goal, (3, 2));
        assert_eq!(level.tile_center(level.goal), (56.0, 24.0));
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
