# k8s/ · GCP 쿠버네티스(GKE Autopilot) 배포

접속 주소: **https://8-232-203-94.sslip.io** (손님) · `/pickup` (호출 화면) · `/kitchen` (주방)

| 파일 | 내용 |
|---|---|
| `postgres.yaml` | 데이터베이스 (5Gi 디스크). 비밀번호는 Secret `db-secret` |
| `model.yaml` | 음성 인식 서버. CPU 2 · 메모리 3Gi, 준비 확인 `/ready` |
| `backend.yaml` | 백엔드 |
| `frontend.yaml` | 화면(Nginx). https 입구 뒤에서만 받음, 요청 대기 60초 |
| `ingress.yaml` · `managed-cert.yaml` | https 입구 + 구글 무료 인증서 (`<IP>.sslip.io`). http 로 오면 https 로 보냄 |

## 새 버전 배포 (평소)
`main` 을 최신으로 받은 뒤 저장소 맨 위 폴더에서:
- Windows: `powershell -ExecutionPolicy Bypass -File scripts/deploy.ps1`
- macOS: `bash scripts/deploy.sh`
- 배포 전에 상태를 백업하고, 배포 후 `k8s/DEPLOY_LOG.md` 맨 위에 한 줄 기록 (문제가 생기면 `bash scripts/rollback.sh <이전 태그>`)

## 처음 한 번만 (2026-10-19 에 해 둠)
```
gcloud services enable container.googleapis.com artifactregistry.googleapis.com compute.googleapis.com
gcloud artifacts repositories create fundamental1 --repository-format=docker --location=asia-northeast3
gcloud auth configure-docker asia-northeast3-docker.pkg.dev
gcloud container clusters create-auto fundamental1-cluster --region=asia-northeast3
gcloud compute addresses create fundamental1-ip --global
# 노드가 이미지 보관함을 읽을 수 있게 (새 프로젝트는 기본 권한이 없어 403 ImagePullBackOff 가 남)
gcloud artifacts repositories add-iam-policy-binding fundamental1 --location=asia-northeast3 \
  --member=serviceAccount:<프로젝트번호>-compute@developer.gserviceaccount.com --role=roles/artifactregistry.reader
kubectl apply -f k8s/namespace.yaml
kubectl -n fundamental1 create secret generic db-secret --from-literal=POSTGRES_USER=app --from-literal=POSTGRES_PASSWORD=<무작위값> --from-literal=POSTGRES_DB=app
```
- 고정 IP 가 바뀌면 `managed-cert.yaml` 의 도메인과 배포 스크립트의 `DOMAIN` 을 같이 바꾼다.
- 인증서 상태: `kubectl -n fundamental1 get managedcertificate` → `Active` 이면 https 사용 가능 (처음 15~60분)

## Windows 주의
- PowerShell 에서 `gcloud` 가 "스크립트를 실행할 수 없음"이면 `gcloud.cmd` 로 실행한다.
- `gcloud init` 을 **관리자 창에서 하지 않는다.** 하면 로그인 정보 폴더가 잠겨 kubectl 연결이 안 된다. 이미 했다면 관리자 창에서
  `icacls "$env:APPDATA\gcloud" /setowner "$env:USERNAME" /T` 와 `icacls "$env:APPDATA\gcloud" /grant "${env:USERNAME}:(OI)(CI)F" /T`

## 운영 명령
| 하고 싶은 일 | 명령 |
|---|---|
| 상태 보기 | `kubectl -n fundamental1 get pods,ingress,managedcertificate` |
| 로그 보기 | `kubectl -n fundamental1 logs deploy/backend` (model, frontend 도 같음) |
| 직전 버전으로 되돌리기 | `kubectl -n fundamental1 rollout undo deployment/backend` |
| 화면·백엔드·모델을 한 버전으로 되돌리기 | `bash scripts/rollback.sh <태그>` (태그·기록: `k8s/DEPLOY_LOG.md`) |
| 잠시 모두 끄기 (CPU 요금 절약) | `kubectl -n fundamental1 scale deploy --all --replicas=0` 과 `kubectl -n fundamental1 scale statefulset postgres --replicas=0` |
| 다시 켜기 | 위 명령에서 `--replicas=1` |
| 시연 전 테스트 쿠폰 초기화 | `curl -X POST -d "" https://8-232-203-94.sslip.io/api/demo/reset-coupons` |
| **완전히 정리 (발표 후)** | `gcloud container clusters delete fundamental1-cluster --region=asia-northeast3` · `gcloud compute addresses delete fundamental1-ip --global` · `gcloud artifacts repositories delete fundamental1 --location=asia-northeast3` |

※ 주방 화면·쿠폰 초기화에는 잠금이 없습니다(데모용). 주소를 팀 밖에 널리 공유하지 마세요.
