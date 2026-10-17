#!/usr/bin/env bash
# Install Node LTS user-local (D20): official tarball, SHA-256 verified, no sudo, no Homebrew.
# Node is MIT licensed. macOS arm64 only.
set -euo pipefail

NODE_VERSION="v24.22.0"
ARCH="darwin-arm64"
DEST="$HOME/.local/node"
NAME="node-${NODE_VERSION}-${ARCH}"
BASE="https://nodejs.org/dist/${NODE_VERSION}"

if [ -e "$DEST" ]; then
  echo "refusing to overwrite existing $DEST" >&2
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
curl -fsSLO "${BASE}/${NAME}.tar.gz"
curl -fsSLO "${BASE}/SHASUMS256.txt"
grep " ${NAME}.tar.gz\$" SHASUMS256.txt | shasum -a 256 -c -
tar -xzf "${NAME}.tar.gz"
mkdir -p "$HOME/.local"
mv "$NAME" "$DEST"
"$DEST/bin/node" --version
"$DEST/bin/npm" --version
"$DEST/bin/npx" --version
