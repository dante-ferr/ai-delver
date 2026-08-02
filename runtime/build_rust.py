import os
import subprocess
import shutil
import sys
import sysconfig


def _collect_rust_sources(src_root: str) -> list[str]:
    # Include .toml: define_config! embeds them via include_str! at compile time.
    source_files = []
    for root, _, files in os.walk(src_root):
        for file_name in files:
            if file_name.endswith((".rs", ".toml")):
                source_files.append(os.path.join(root, file_name))
    return source_files


def _resolve_cargo_release_lib(script_dir: str) -> str:
    candidates = []
    cargo_target_dir = os.environ.get("CARGO_TARGET_DIR")
    if cargo_target_dir:
        candidates.append(os.path.join(cargo_target_dir, "release", "libruntime_core.so"))
    candidates.extend(
        [
            os.path.join(script_dir, "target", "release", "libruntime_core.so"),
            os.path.join(script_dir, "target", "release", "libruntime_core.dylib"),
            os.path.join(script_dir, "target", "release", "runtime_core.dll"),
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cargo_toml = os.path.join(script_dir, "Cargo.toml")
    src_root = os.path.join(script_dir, "src")

    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not suffix:
        suffix = ".so"

    dst = os.path.join(script_dir, "runtime", f"runtime_core{suffix}")

    # Always ask Cargo to build. Skipping based on the copied .so mtime previously
    # left a stale release artifact in place after source edits (dst mtime refreshed
    # by copy while cargo thought release was already up to date).
    cargo_jobs = os.getenv("RUNTIME_CARGO_JOBS", "1")
    env = os.environ.copy()
    env["PYO3_PYTHON"] = os.path.realpath(sys.executable)
    print(f"Compiling Rust core (jobs={cargo_jobs})...")
    print(f"  sources under {src_root} ({len(_collect_rust_sources(src_root))} files)")
    subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--jobs",
            cargo_jobs,
            "--manifest-path",
            cargo_toml,
        ],
        check=True,
        env=env,
    )

    src = _resolve_cargo_release_lib(script_dir)
    if not os.path.exists(src):
        raise FileNotFoundError(f"cargo release library not found (looked for {src})")

    shutil.copy(src, dst)
    src_mtime = os.path.getmtime(src)
    print(f"✅ Copied {src}")
    print(f"   → {dst}")
    print(f"   artifact mtime={src_mtime:.0f} size={os.path.getsize(dst)} bytes")


if __name__ == "__main__":
    build()
