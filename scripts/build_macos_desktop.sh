#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This build script only runs on macOS." >&2
  exit 2
fi

UV_BIN="${UV:-uv}"
APP_NAME="ESE Control Center"
BUNDLE_ID="${BUNDLE_ID:-com.bdblabs.ese-control-center}"
ARCH="$(uname -m)"
DIST_ROOT="${ROOT_DIR}/dist/macos"
BUILD_ROOT="${ROOT_DIR}/build/macos"
PYINSTALLER_ROOT="${ROOT_DIR}/build/pyinstaller"
ICON_ROOT="${BUILD_ROOT}/icon"
ICONSET_DIR="${ICON_ROOT}/ESEControlCenter.iconset"
ICON_PNG="${ICON_ROOT}/ESEControlCenter.png"
ICON_ICNS="${ICON_ROOT}/ESEControlCenter.icns"
STAGING_DIR="${BUILD_ROOT}/dmg-staging"
DMG_PATH="${DIST_ROOT}/ESE-Control-Center-macOS-${ARCH}.dmg"

mkdir -p "${DIST_ROOT}" "${BUILD_ROOT}" "${ICON_ROOT}"

echo "Syncing desktop and packaging dependencies..."
"${UV_BIN}" sync --group dev --group desktop --group packaging

echo "Generating branded icon assets..."
"${UV_BIN}" run python scripts/generate_desktop_icon.py --output "${ICON_PNG}"

rm -rf "${ICONSET_DIR}"
mkdir -p "${ICONSET_DIR}"

for size in 16 32 64 128 256 512; do
  sips -z "${size}" "${size}" "${ICON_PNG}" --out "${ICONSET_DIR}/icon_${size}x${size}.png" >/dev/null
  retina_size=$((size * 2))
  sips -z "${retina_size}" "${retina_size}" "${ICON_PNG}" --out "${ICONSET_DIR}/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "${ICONSET_DIR}" -o "${ICON_ICNS}"

echo "Building macOS app bundle with PyInstaller..."
rm -rf "${ROOT_DIR}/dist/${APP_NAME}.app" "${PYINSTALLER_ROOT}" "${ROOT_DIR}/__pycache__"
"${UV_BIN}" run pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "${APP_NAME}" \
  --icon "${ICON_ICNS}" \
  --osx-bundle-identifier "${BUNDLE_ID}" \
  --collect-all webview \
  --distpath "${ROOT_DIR}/dist" \
  --workpath "${PYINSTALLER_ROOT}/build" \
  --specpath "${PYINSTALLER_ROOT}/spec" \
  packaging/macos/launcher.py

APP_BUNDLE="${ROOT_DIR}/dist/${APP_NAME}.app"
if [[ ! -d "${APP_BUNDLE}" ]]; then
  echo "Expected app bundle not found: ${APP_BUNDLE}" >&2
  exit 3
fi

mkdir -p "${DIST_ROOT}"
rm -rf "${DIST_ROOT}/${APP_NAME}.app"
mv "${APP_BUNDLE}" "${DIST_ROOT}/${APP_NAME}.app"

if [[ -n "${APPLE_DEVELOPER_IDENTITY:-}" ]]; then
  echo "Code signing app bundle with ${APPLE_DEVELOPER_IDENTITY}..."
  codesign --force --deep --options runtime --sign "${APPLE_DEVELOPER_IDENTITY}" "${DIST_ROOT}/${APP_NAME}.app"
fi

echo "Preparing DMG staging area..."
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"
cp -R "${DIST_ROOT}/${APP_NAME}.app" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

echo "Building DMG..."
rm -f "${DMG_PATH}"
hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}" >/dev/null

if [[ -n "${APPLE_DEVELOPER_IDENTITY:-}" ]]; then
  echo "Code signing DMG..."
  codesign --force --sign "${APPLE_DEVELOPER_IDENTITY}" "${DMG_PATH}"
fi

cat <<EOF
Build complete:
  App bundle: ${DIST_ROOT}/${APP_NAME}.app
  DMG:        ${DMG_PATH}

Optional notarization:
  xcrun notarytool submit "${DMG_PATH}" --apple-id <id> --team-id <team> --password <app-specific-password> --wait
EOF
