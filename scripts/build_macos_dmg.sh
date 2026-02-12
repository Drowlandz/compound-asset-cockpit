#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script only supports macOS."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-macos-build}"
APP_NAME="${APP_NAME:-IM}"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"
DMG_STAGING="$DIST_DIR/dmg-staging"
DMG_PATH="$DIST_DIR/${APP_NAME}.dmg"
APP_PATH="$DIST_DIR/${APP_NAME}.app"

echo "Using Python: $PYTHON_BIN"
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt pyinstaller

rm -rf "$DIST_DIR" "$BUILD_DIR" "$ROOT_DIR/${APP_NAME}.spec"

pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --collect-all streamlit \
  --collect-all streamlit_echarts \
  --collect-all yfinance \
  --hidden-import yfinance \
  --add-data "app.py:." \
  --add-data "config.py:." \
  --add-data "data_manager.py:." \
  --add-data "utils.py:." \
  --add-data "ui.py:." \
  --add-data "services:services" \
  --add-data "assets:assets" \
  run_app.py

if [[ ! -d "$APP_PATH" ]]; then
  echo "Build failed: $APP_PATH not found."
  exit 1
fi

SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:--}"
SIGN_ENTITLEMENTS="${MACOS_SIGN_ENTITLEMENTS:-}"
if [[ -n "$SIGN_ENTITLEMENTS" && ! -f "$SIGN_ENTITLEMENTS" ]]; then
  echo "Entitlements file not found: $SIGN_ENTITLEMENTS"
  exit 1
fi

echo "Signing app with identity: $SIGN_IDENTITY"
CODESIGN_ARGS=(--force --deep --sign "$SIGN_IDENTITY")
if [[ "$SIGN_IDENTITY" != "-" ]]; then
  CODESIGN_ARGS+=(--options runtime --timestamp)
fi
if [[ -n "$SIGN_ENTITLEMENTS" ]]; then
  CODESIGN_ARGS+=(--entitlements "$SIGN_ENTITLEMENTS")
fi
codesign "${CODESIGN_ARGS[@]}" "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "$APP_PATH" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

rm -f "$DMG_PATH"
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$DMG_STAGING" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Build complete:"
echo "  App: $APP_PATH"
echo "  DMG: $DMG_PATH"
if [[ "$SIGN_IDENTITY" == "-" ]]; then
  echo "  Note: ad-hoc signature is for local testing only."
  echo "        For other Macs, use Developer ID signing (+ notarization)."
fi
