#!/usr/bin/env bash
# 학습한 음성 인식 모델(약 250MB)을 팀 저장소 GitHub Release 에서 받아 model/weights/ 에 넣는다.
# 모델 파일은 Git 에 올리지 않으므로, 모델 서버 이미지를 빌드하기 전에 꼭 실행한다. (gh auth login 필요)
#   bash model/scripts/fetch_model.sh
set -euo pipefail

TAG="${1:-model-whisper-small-elderly-v1}"
NAME=whisper-small-elderly-v1

cd "$(dirname "$0")/../weights"
if [ -f "$NAME/model.bin" ]; then
  echo "✅ 이미 있음: model/weights/$NAME"
  exit 0
fi
gh release download "$TAG" --pattern "$NAME.zip" --clobber
unzip -q -o "$NAME.zip"
rm -f "$NAME.zip"
test -f "$NAME/model.bin"
echo "✅ 받음: model/weights/$NAME ($(du -sh "$NAME" | cut -f1))"
