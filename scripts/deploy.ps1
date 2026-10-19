# GCP 쿠버네티스(GKE) 배포 스크립트 (Windows)
# 실행: 저장소 맨 위 폴더에서  powershell -ExecutionPolicy Bypass -File scripts/deploy.ps1
# 처음 한 번은 03_k8s_gcp_deploy.md 대로 클러스터·이미지 보관함·db-secret 을 먼저 만들어야 한다.
$ErrorActionPreference = "Stop"

$PROJECT_ID = "project-b10d899d-6de4-4ec8-a03"
$REGION = "asia-northeast3"
$CLUSTER = "fundamental1-cluster"
$NS = "fundamental1"
$REGISTRY = "$REGION-docker.pkg.dev/$PROJECT_ID/fundamental1"
$DOMAIN = "8-232-203-94.sslip.io"

function Run([string]$cmd) {
    Write-Host "> $cmd" -ForegroundColor Cyan
    cmd /c "$cmd"
    if ($LASTEXITCODE -ne 0) { throw "실패: $cmd" }
}

# 1. 학습한 모델 파일 확인 (음성 인식 + 의도 파악 분류·생성). 없으면 Release 에서 받는다
if (-not (Test-Path "model/weights/whisper-small-elderly-v1/model.bin")) {
    Run "bash model/scripts/fetch_model.sh"
}
Run "bash model/scripts/fetch_nlu_model.sh"

# 2. 이미지 만들어 올리기 (태그 = 지금 커밋)
$TAG = (git rev-parse --short HEAD).Trim()
foreach ($svc in @("frontend", "backend", "model")) {
    Run "docker buildx build --platform linux/amd64 -t $REGISTRY/${svc}:$TAG -t $REGISTRY/${svc}:latest --push ./$svc"
}

# 3. 쿠버네티스에 적용하고 새 이미지로 바꾸기
Run "gcloud.cmd container clusters get-credentials $CLUSTER --region=$REGION --project=$PROJECT_ID"
Run "kubectl apply -k k8s"
foreach ($svc in @("frontend", "backend", "model")) {
    Run "kubectl -n $NS set image deployment/$svc $svc=$REGISTRY/${svc}:$TAG"
}
foreach ($svc in @("model", "backend", "frontend")) {
    Run "kubectl -n $NS rollout status deployment/$svc --timeout=600s"
}

# 4. 결과
Run "kubectl -n $NS get pods"
Run "kubectl -n $NS get managedcertificate fundamental1-cert"
Write-Host ""
Write-Host "접속 주소: https://$DOMAIN  (인증서가 Active 가 되기 전에는 https 가 열리지 않을 수 있음, 처음 15~60분)" -ForegroundColor Green
Write-Host "  손님 화면 https://$DOMAIN   호출 화면 https://$DOMAIN/pickup   주방 화면 https://$DOMAIN/kitchen"
