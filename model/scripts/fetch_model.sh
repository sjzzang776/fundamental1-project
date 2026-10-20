#!/usr/bin/env bash
# 학습한 음성 인식 모델(약 250MB)을 팀 저장소 GitHub Release 에서 받아 model/weights/ 에 넣는다.
# 모델 파일은 Git 에 올리지 않으므로, 모델 서버 이미지를 빌드하기 전에 꼭 실행한다. (공개 Release 라 로그인 없이 받음)
# AI Hub 데이터로 학습한 모델: 쓸 때 "한국지능정보사회진흥원 AI 허브 데이터 사용"을 밝혀야 한다 (README 참고)
#   bash model/scripts/fetch_model.sh
set -euo pipefail

TAG="${1:-model-whisper-small-elderly-v1}"
NAME=whisper-small-elderly-v1

cd "$(dirname "$0")/../weights"
if [ -f "$NAME/model.bin" ]; then
  echo "✅ 이미 있음: model/weights/$NAME"
  exit 0
fi
curl -fL --retry 3 -o "$NAME.zip" "https://github.com/sjzzang776/fundamental1-project/releases/download/$TAG/$NAME.zip"
unzip -q -o "$NAME.zip"
rm -f "$NAME.zip"
test -f "$NAME/model.bin"
echo "✅ 받음: model/weights/$NAME ($(du -sh "$NAME" | cut -f1))"
