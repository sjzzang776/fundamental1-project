#!/usr/bin/env bash
# GKE 배포 되돌리기. 새 버전에 문제가 있으면 실행한다. (기록: k8s/DEPLOY_LOG.md)
#   bash scripts/rollback.sh 253dc8f   # 그 태그(커밋) 이미지로 화면·백엔드·모델 서버를 모두 되돌림 (권장)
#   bash scripts/rollback.sh           # 태그 없이: 셋 다 바로 전 버전으로 (kubectl rollout undo)
# 이미지 보관함의 예전 태그 이미지는 지우지 않으므로 언제든 되돌릴 수 있다.
# DB 는 건드리지 않는다. DB 까지 되돌려야 하면 DEPLOY_LOG.md 의 "DB 되돌리기" 참고.
# Windows: Git Bash 에서 실행. gcloud 가 PATH 에 없으면 아래 줄이 Cloud SDK bin 을 붙인다.
set -euo pipefail

PROJECT_ID="project-b10d899d-6de4-4ec8-a03"
REGION="asia-northeast3"
CLUSTER="fundamental1-cluster"
NS="fundamental1"
REGISTRY="$REGION-docker.pkg.dev/$PROJECT_ID/fundamental1"
SDK_BIN="${LOCALAPPDATA:-}/Google/Cloud SDK/google-cloud-sdk/bin"
[ -d "$SDK_BIN" ] && export PATH="$SDK_BIN:$PATH"
GCLOUD=$(command -v gcloud.cmd || command -v gcloud)  # Windows Git Bash 는 gcloud.cmd 여야 경로 문제가 없음

"$GCLOUD" container clusters get-credentials "$CLUSTER" --region="$REGION" --project="$PROJECT_ID" >/dev/null

echo "== 지금 이미지"
kubectl -n "$NS" get deploy -o custom-columns=NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image

TAG="${1:-}"
for svc in model backend frontend; do
  if [ -n "$TAG" ]; then
    kubectl -n "$NS" set image "deployment/$svc" "$svc=$REGISTRY/$svc:$TAG"
  else
    kubectl -n "$NS" rollout undo "deployment/$svc"
  fi
done
for svc in model backend frontend; do
  kubectl -n "$NS" rollout status "deployment/$svc" --timeout=600s
done

echo "== 되돌린 뒤 이미지"
kubectl -n "$NS" get deploy -o custom-columns=NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image
echo "※ k8s/model.yaml 의 CPU·메모리 설정은 그대로입니다. 예전 설정까지 되돌리려면 DEPLOY_LOG.md 의 백업 all.yaml 참고."
echo "※ 되돌렸으면 k8s/DEPLOY_LOG.md 에 한 줄 기록해 주세요."
