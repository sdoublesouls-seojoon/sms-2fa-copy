#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="2fa"
VERSION="${1:-0.1.0}"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

cd "$PROJECT_DIR"

echo "==> 기존 빌드 정리..."
rm -rf build dist

echo "==> 가상환경 설정..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt py2app

echo "==> py2app 빌드..."
python setup.py py2app

echo "==> DMG 생성..."
mkdir -p dist/dmg
cp -R "dist/${APP_NAME}.app" dist/dmg/

# Applications 폴더 심볼릭 링크 추가
ln -s /Applications dist/dmg/Applications

hdiutil create -volname "$APP_NAME" \
    -srcfolder dist/dmg \
    -ov -format UDZO \
    "dist/${DMG_NAME}"

rm -rf dist/dmg

echo "==> 빌드 완료: dist/${DMG_NAME}"
