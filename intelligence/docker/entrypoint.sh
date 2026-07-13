#!/bin/sh
set -e

# Named Docker volumes for cargo/target are created as root. The compose file
# runs the trainer as the host UID:GID, so fix ownership before cargo starts.
HOST_UID="${HOST_UID:-${UID:-1000}}"
HOST_GID="${HOST_GID:-${GID:-1000}}"

fix_owned() {
  dir="$1"
  mkdir -p "$dir"
  if [ "$(id -u)" = "0" ]; then
    chown -R "${HOST_UID}:${HOST_GID}" "$dir" 2>/dev/null || true
  fi
}

fix_owned "${CARGO_HOME:-/usr/local/cargo}/registry"
fix_owned "${CARGO_HOME:-/usr/local/cargo}/git"
fix_owned /app/intelligence/target

if [ "$(id -u)" = "0" ] && [ -n "$1" ]; then
  if command -v setpriv >/dev/null 2>&1; then
    if setpriv --reuid="${HOST_UID}" --regid="${HOST_GID}" --init-groups -- true 2>/dev/null; then
      exec setpriv --reuid="${HOST_UID}" --regid="${HOST_GID}" --init-groups -- "$@"
    fi
    exec setpriv --reuid="${HOST_UID}" --regid="${HOST_GID}" --clear-groups -- "$@"
  fi
  if command -v runuser >/dev/null 2>&1; then
    exec runuser -u "#${HOST_UID}" -g "#${HOST_GID}" -- "$@"
  fi
fi

exec "$@"
