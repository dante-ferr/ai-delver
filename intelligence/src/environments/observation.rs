//! Shared observation geometry for the Delver's local visual window.
//!
//! Radius 12 yields a 25×25 occupancy grid (625 cells), enough to see across
//! 8-tile pits before jumping, without
//! the full noise cost of a radius-14 window.

/// Tiles from the Delver's cell to each edge of the local view (inclusive span).
pub const LOCAL_VIEW_RADIUS: i32 = 12;

/// Side length of the square local view (`2 * radius + 1`).
pub const LOCAL_VIEW_SIDE: usize = (LOCAL_VIEW_RADIUS as usize) * 2 + 1;

/// Flattened local-view cell count (`side²`).
pub const LOCAL_VIEW_CELLS: usize = LOCAL_VIEW_SIDE * LOCAL_VIEW_SIDE;

/// Global proprioceptive / goal features concatenated beside the local view.
pub const GLOBAL_STATE_SIZE: usize = 7;
