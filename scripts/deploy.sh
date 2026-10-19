#!/usr/bin/env bash
# GCP 쿠버네티스(GKE) 배포 스크립트 (macOS / Linux / Git Bash)
# 실행: 저장소 맨 위 폴더에서  bash scripts/deploy.sh
# 처음 한 번은 03_k8s_gcp_deploy.md 대로 클러스터·이미지 보관함·db-secret 을 먼저 만들어야 한다.
set -euo pipefail

PROJECT_ID="project-b10d899d-6de4-4ec8-a03"
REGION="asia-northeast3"
CLUSTER="fundamental1-cluster"
NS="fundamental1"
REGISTRY="$REGION-docker.pkg.dev/$PROJECT_ID/fundamental1"
DOMAIN="8-232-203-94.sslip.io"

# 1. 학습한 음성 인식 모델 파일 확인 (없으면 원본 모델로 만들어지고 켤 때마다 464MB를 받는다)
[ -f model/weights/whisper-small-elderly-v1/model.bin ] || bash model/scripts/fetch_model.sh

# 2. 이미지 만들어 올리기 (태그 = 지금 커밋). Apple Silicon Mac 에서도 amd64 로 만든다
TAG="$(git rev-parse --short HEAD)"
for svc in frontend backend model; do
  docker buildx build --platform linux/amd64 -t "$REGISTRY/$svc:$TAG" -t "$REGISTRY/$svc:latest" --push "./$svc"
done

# 3. 쿠버네티스에 적용하고 새 이미지로 바꾸기
gcloud container clusters get-credentials "$CLUSTER" --region="$REGION" --project="$PROJECT_ID"
kubectl apply -k k8s
for svc in frontend backend model; do
  kubectl -n "$NS" set image "deployment/$svc" "$svc=$REGISTRY/$svc:$TAG"
done
for svc in model backend frontend; do
  kubectl -n "$NS" rollout status "deployment/$svc" --timeout=600s
done

# 4. 결과
kubectl -n "$NS" get pods
kubectl -n "$NS" get managedcertificate fundamental1-cert
echo
echo "접속 주소: https://$DOMAIN  (인증서가 Active 가 되기 전에는 https 가 열리지 않을 수 있음, 처음 15~60분)"
echo "  손님 화면 https://$DOMAIN   호출 화면 https://$DOMAIN/pickup   주방 화면 https://$DOMAIN/kitchen"
