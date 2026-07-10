import os
import subprocess
import shutil
import sys
import sysconfig


def _collect_rust_sources(src_root: str) -> list[str]:
    source_files = []
    for root, _, files in os.walk(src_root):
        for file_name in files:
            if file_name.endswith(".rs"):
                source_files.append(os.path.join(root, file_name))
    return source_files


def _is_rebuild_needed(output_binary: str, source_paths: list[str]) -> bool:
    if not os.path.exists(output_binary):
        return True
    output_mtime = os.path.getmtime(output_binary)
    return any(os.path.getmtime(path) > output_mtime for path in source_paths if os.path.exists(path))


def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cargo_toml = os.path.join(script_dir, "Cargo.toml")
    cargo_lock = os.path.join(script_dir, "Cargo.lock")
    src_root = os.path.join(script_dir, "src")

    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not suffix:
        suffix = ".so"

    src = os.path.join(script_dir, "target", "release", "libruntime_core.so")
    if not os.path.exists(src):
        src = os.path.join(script_dir, "target", "release", "libruntime_core.dylib")
    if not os.path.exists(src):
        src = os.path.join(script_dir, "target", "release", "runtime_core.dll")

    dst = os.path.join(script_dir, "runtime", f"runtime_core{suffix}")

    source_paths = [cargo_toml, cargo_lock, *_collect_rust_sources(src_root)]
    if _is_rebuild_needed(dst, source_paths):
        cargo_jobs = os.getenv("RUNTIME_CARGO_JOBS", "1")
        env = os.environ.copy()
        env["PYO3_PYTHON"] = os.path.realpath(sys.executable)
        print(f"Compiling Rust core (jobs={cargo_jobs})...")
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
    else:
        print(f"Rust core already up-to-date: {dst}")

    shutil.copy(src, dst)
    print(f"✅ Successfully copied {src} to {dst}")


if __name__ == "__main__":
    build()
