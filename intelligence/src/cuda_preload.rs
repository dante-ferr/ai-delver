use std::{
    ffi::CString,
    fs,
    path::{Path, PathBuf},
};

/// GNU ld `--as-needed` often drops `libtorch_cuda` from the binary's NEEDED
/// entries. PyTorch then reports CUDA as unavailable until the CUDA libs are
/// loaded into the process. Force-load them before any device queries.
pub fn ensure_torch_cuda_loaded() {
    let Some(dir) = libtorch_lib_dir() else {
        return;
    };
    // Load CUDA runtime first, then c10_cuda, then libtorch_cuda.
    let mut ordered = Vec::new();
    if let Ok(entries) = fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if name.starts_with("libcudart") && name.contains(".so") {
                ordered.push(entry.path());
            }
        }
    }
    for name in ["libc10_cuda.so", "libtorch_cuda.so"] {
        let path = dir.join(name);
        if path.exists() {
            ordered.push(path);
        }
    }
    for path in ordered {
        dlopen_global(&path);
    }
}

fn libtorch_lib_dir() -> Option<PathBuf> {
    if let Some(cpu) = find_lib("libtorch_cpu.so") {
        return cpu.parent().map(Path::to_path_buf);
    }
    if let Some(cuda) = find_lib("libtorch_cuda.so") {
        return cuda.parent().map(Path::to_path_buf);
    }
    None
}

fn find_lib(needle: &str) -> Option<PathBuf> {
    if let Ok(maps) = fs::read_to_string("/proc/self/maps") {
        for line in maps.lines() {
            if let Some(path) = line.split_whitespace().last() {
                if path.ends_with(needle) {
                    return Some(PathBuf::from(path));
                }
            }
        }
    }
    if let Ok(ld) = std::env::var("LD_LIBRARY_PATH") {
        for dir in ld.split(':').filter(|d| !d.is_empty()) {
            let candidate = Path::new(dir).join(needle);
            if candidate.exists() {
                return Some(candidate);
            }
        }
    }
    None
}

fn dlopen_global(path: &Path) {
    let Ok(c_path) = CString::new(path.to_string_lossy().as_bytes()) else {
        return;
    };
    unsafe {
        libc::dlopen(c_path.as_ptr(), libc::RTLD_NOW | libc::RTLD_GLOBAL);
    }
}
