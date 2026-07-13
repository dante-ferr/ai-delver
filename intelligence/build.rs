use std::path::PathBuf;

fn main() {
    // Prefer an rpath so the binary finds the downloaded libtorch without
    // requiring the user to export LD_LIBRARY_PATH (CUDA preload still helps
    // when ld --as-needed drops libtorch_cuda from DT_NEEDED).
    if let Ok(lib_dir) = std::env::var("DEP_TCH_LIBTORCH_LIB") {
        let lib_dir = PathBuf::from(lib_dir);
        println!("cargo:rustc-link-arg=-Wl,-rpath,{}", lib_dir.display());
        println!("cargo:rerun-if-env-changed=DEP_TCH_LIBTORCH_LIB");
    }
}
