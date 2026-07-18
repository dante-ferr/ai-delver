//! Shared TOML config loading for entity and world archetypes.

/// Defines a config struct whose values come from an embedded TOML file.
///
/// Each invocation only declares field names and types. Deserialize, `from_toml_str`,
/// `load`, and `Default` (from the embedded file) are generated automatically.
///
/// The `file:` path is relative to the crate root (`CARGO_MANIFEST_DIR`).
#[macro_export]
macro_rules! define_config {
    (
        $(#[$meta:meta])*
        pub struct $name:ident,
        file: $file:literal,
        {
            $(
                $(#[$field_meta:meta])*
                pub $field:ident: $ty:ty
            ),* $(,)?
        }
    ) => {
        $(#[$meta])*
        #[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
        #[serde(deny_unknown_fields)]
        pub struct $name {
            $(
                $(#[$field_meta])*
                pub $field: $ty,
            )*
        }

        impl $name {
            /// Parse config from a TOML string.
            pub fn from_toml_str(text: &str) -> anyhow::Result<Self> {
                Ok(toml::from_str(text)?)
            }

            /// Load config from a filesystem path.
            pub fn load(path: &std::path::Path) -> anyhow::Result<Self> {
                let text = std::fs::read_to_string(path).map_err(|err| {
                    anyhow::anyhow!("failed to read config {}: {err}", path.display())
                })?;
                Self::from_toml_str(&text).map_err(|err| {
                    anyhow::anyhow!("invalid config {}: {err}", path.display())
                })
            }

            const EMBEDDED_TOML: &'static str =
                include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/", $file));
        }

        impl Default for $name {
            fn default() -> Self {
                Self::from_toml_str(Self::EMBEDDED_TOML)
                    .unwrap_or_else(|err| panic!("invalid embedded config {}: {err}", $file))
            }
        }
    };
}
