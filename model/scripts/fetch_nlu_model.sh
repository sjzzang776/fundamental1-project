#!/usr/bin/env bash
# 학습한 의도 파악 분류 모델(nlu-intent-v1)을 팀 저장소 GitHub Release 에서 받아 model/weights/ 에 넣는다.
# 모델 서버 이미지를 빌드하기 전에 실행한다. 없어도 서버는 돌아간다 (규칙 + Claude 만 씀). (gh auth login 필요)
#   bash model/scripts/fetch_nlu_model.sh
set -euo pipefail

TAG="${1:-model-nlu-intent-v1}"
NAME=nlu-intent-v1

cd "$(dirname "$0")/../weights"
if [ -f "$NAME/model.onnx" ]; then
  echo "✅ 이미 있음: model/weights/$NAME"
  exit 0
fi
gh release download "$TAG" --pattern "$NAME.zip" --clobber
unzip -q -o "$NAME.zip"
rm -f "$NAME.zip"
test -f "$NAME/model.onnx"
echo "✅ 받음: model/weights/$NAME ($(du -sh "$NAME" | cut -f1))"
