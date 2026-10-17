#!/usr/bin/env bash
# Install a user-local container runtime (D20, D30; PRD "Packaging"): no sudo, no Homebrew.
# Dev-machine tooling only, not shipped code. macOS arm64 only.
#   Lima    v2.2.1   Apache-2.0  https://github.com/lima-vm/lima        (SHA256SUMS)
#   Colima  v0.10.3  MIT         https://github.com/abiosoft/colima     (.sha256sum)
#   Docker CLI 29.8.2 Apache-2.0 https://download.docker.com/mac/static/stable/aarch64/
#           download.docker.com publishes no checksum file for the static CLI, so the hash
#           below was recorded on first download (2026-10-17) and is pinned here.
#   Compose v5.6.0   Apache-2.0  https://github.com/docker/compose      (.sha256)
# Each archive goes into its own new directory under ~/.local/src/<tool>/, is verified
# before extraction, and only the verified binary is moved into ~/.local/bin.
set -euo pipefail

LIMA_VERSION="2.2.1"
COLIMA_VERSION="0.10.3"
DOCKER_VERSION="29.8.2"
DOCKER_SHA256="5ffa2bafbabe073470f0333f4a129599230b73d1170bb61146b3d9b08e1d1325"
COMPOSE_VERSION="5.6.0"

BIN="$HOME/.local/bin"
SHARE="$HOME/.local/share"
SRC="$HOME/.local/src"
PLUGINS="$HOME/.docker/cli-plugins"

[ "$(uname -s)-$(uname -m)" = "Darwin-arm64" ] || { echo "macOS arm64 only" >&2; exit 1; }

for f in "$BIN/limactl" "$BIN/colima" "$BIN/docker" "$PLUGINS/docker-compose" "$SHARE/lima"; do
  if [ -e "$f" ]; then echo "refusing to overwrite existing $f" >&2; exit 1; fi
done

newdir() {  # a fresh, empty download directory per tool
  local d="$SRC/$1"
  if [ -e "$d" ]; then echo "refusing to reuse existing $d" >&2; exit 1; fi
  mkdir -p "$d"; echo "$d"
}

mkdir -p "$BIN" "$SHARE" "$PLUGINS"

# --- Lima (limactl + share/lima guest agents) ---
D="$(newdir lima)"
LIMA_TGZ="lima-${LIMA_VERSION}-Darwin-arm64.tar.gz"
curl -fsSL -o "$D/$LIMA_TGZ" "https://github.com/lima-vm/lima/releases/download/v${LIMA_VERSION}/${LIMA_TGZ}"
curl -fsSL -o "$D/SHA256SUMS" "https://github.com/lima-vm/lima/releases/download/v${LIMA_VERSION}/SHA256SUMS"
(cd "$D" && grep " ${LIMA_TGZ}\$" SHA256SUMS | shasum -a 256 -c -)
mkdir "$D/x" && tar -xzf "$D/$LIMA_TGZ" -C "$D/x"
mv "$D/x/bin/"* "$BIN/"
mv "$D/x/share/lima" "$SHARE/lima"

# --- Colima ---
D="$(newdir colima)"
curl -fsSL -o "$D/colima-Darwin-arm64" "https://github.com/abiosoft/colima/releases/download/v${COLIMA_VERSION}/colima-Darwin-arm64"
curl -fsSL -o "$D/colima-Darwin-arm64.sha256sum" "https://github.com/abiosoft/colima/releases/download/v${COLIMA_VERSION}/colima-Darwin-arm64.sha256sum"
(cd "$D" && shasum -a 256 -c colima-Darwin-arm64.sha256sum)
chmod +x "$D/colima-Darwin-arm64" && mv "$D/colima-Darwin-arm64" "$BIN/colima"

# --- Docker CLI (static) ---
D="$(newdir docker)"
DOCKER_TGZ="docker-${DOCKER_VERSION}.tgz"
curl -fsSL -o "$D/$DOCKER_TGZ" "https://download.docker.com/mac/static/stable/aarch64/${DOCKER_TGZ}"
(cd "$D" && echo "${DOCKER_SHA256}  ${DOCKER_TGZ}" | shasum -a 256 -c -)
mkdir "$D/x" && tar -xzf "$D/$DOCKER_TGZ" -C "$D/x"
mv "$D/x/docker/docker" "$BIN/docker"

# --- Docker Compose plugin ---
D="$(newdir compose)"
curl -fsSL -o "$D/docker-compose-darwin-aarch64" "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-darwin-aarch64"
curl -fsSL -o "$D/docker-compose-darwin-aarch64.sha256" "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-darwin-aarch64.sha256"
(cd "$D" && shasum -a 256 -c docker-compose-darwin-aarch64.sha256)
chmod +x "$D/docker-compose-darwin-aarch64" && mv "$D/docker-compose-darwin-aarch64" "$PLUGINS/docker-compose"

"$BIN/limactl" --version
"$BIN/colima" version
"$BIN/docker" --version
"$BIN/docker" compose version
