use serde_json::Value;
use sha2::{Digest, Sha256};

/// Matches Python `Level.to_hash()`: strip display-only keys, sort object keys,
/// compact JSON, SHA-256 hex digest.
pub fn hash_level_json(value: &Value) -> String {
    let canonical = canonical_json(value);
    format!("{:x}", Sha256::digest(canonical.as_bytes()))
}

fn canonical_json(value: &Value) -> String {
    match value {
        Value::Null => "null".into(),
        Value::Bool(true) => "true".into(),
        Value::Bool(false) => "false".into(),
        Value::Number(number) => number.to_string(),
        Value::String(text) => serde_json::to_string(text).unwrap_or_else(|_| "\"\"".into()),
        Value::Array(items) => {
            let inner = items
                .iter()
                .map(canonical_json)
                .collect::<Vec<_>>()
                .join(",");
            format!("[{inner}]")
        }
        Value::Object(map) => {
            let mut keys: Vec<&String> = map
                .keys()
                .filter(|key| key.as_str() != "display" && key.as_str() != "icon_path")
                .collect();
            keys.sort();
            let inner = keys
                .into_iter()
                .filter_map(|key| {
                    let child = map.get(key)?;
                    let key_json = serde_json::to_string(key).ok()?;
                    Some(format!("{key_json}:{}", canonical_json(child)))
                })
                .collect::<Vec<_>>()
                .join(",");
            format!("{{{inner}}}")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn hash_is_stable_under_key_reordering() {
        let a = json!({"_name": "x", "map": {"b": 1, "a": 2}, "display": {"ignore": true}});
        let b = json!({"map": {"a": 2, "b": 1}, "_name": "x", "icon_path": "nope"});
        assert_eq!(hash_level_json(&a), hash_level_json(&b));
    }
}
