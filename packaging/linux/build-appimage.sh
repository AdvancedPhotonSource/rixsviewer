#!/bin/bash
# packaging/linux/build-appimage.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
VERSION="${1:?Usage: build-appimage.sh <version-tag>}"

rm -rf build dist/rixsviewer dist/AppDir
python3.11 -m PyInstaller packaging/linux/rixsviewer.spec

mkdir -p dist/AppDir/usr/bin
cp -r dist/rixsviewer dist/AppDir/usr/bin/rixsviewer
install -m 755 packaging/linux/AppRun dist/AppDir/AppRun
cp packaging/linux/rixsviewer.desktop dist/AppDir/rixsviewer.desktop
cp src/rixsviewer/assets/icon.png dist/AppDir/rixsviewer.png

curl -sL -o dist/appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x dist/appimagetool

dist/appimagetool --appimage-extract-and-run dist/AppDir "dist/rixsviewer-${VERSION}-x86_64.AppImage"
