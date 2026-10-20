#!/usr/bin/env bash
# 학습한 의도 파악 모델을 팀 저장소 GitHub Release 에서 받아 model/weights/ 에 넣는다.
# - nlu-intent-v1: 분류 모델 (약 70MB)
# - nlu-gen-v1: 생성 모델 (약 1GB). 안 받으려면: NLU_GEN=0 bash model/scripts/fetch_nlu_model.sh
# 모델 서버 이미지를 빌드하기 전에 실행한다. 없어도 서버는 돌아간다 (규칙 + Claude 만 씀). (공개 Release 라 로그인 없이 받음)
#   bash model/scripts/fetch_nlu_model.sh
set -euo pipefail

cd "$(dirname "$0")/../weights"

fetch() {  # fetch <이름> <확인할 파일>
  local name=$1 check=$2
  if [ -f "$name/$check" ]; then
    echo "✅ 이미 있음: model/weights/$name"
    return
  fi
  curl -fL --retry 3 -o "$name.zip" "https://github.com/sjzzang776/fundamental1-project/releases/download/model-$name/$name.zip"
  unzip -q -o "$name.zip"
  rm -f "$name.zip"
  test -f "$name/$check"
  echo "✅ 받음: model/weights/$name ($(du -sh "$name" | cut -f1))"
}

fetch nlu-intent-v1 model.onnx
if [ "${NLU_GEN:-1}" != "0" ]; then
  fetch nlu-gen-v1 model.gguf
fi
