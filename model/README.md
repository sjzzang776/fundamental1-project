# model/ · 음성 인식(STT) 모델 서버

| 주소 | 하는 일 |
|---|---|
| `POST /stt` | 음성(wav/webm, 최대 15초) → 글자. 선택 항목 `hints`(쉼표 구분 단어) |
| `GET /health` | 서버 상태 + `stt_ready`(모델 불러오기 끝났는지) |
| `GET /ready` | 모델 준비됐으면 200, 불러오는 중이면 503 → 쿠버네티스 readinessProbe 용 |
| `POST /predict` | (임시) 연결 테스트 |

## 쓰는 모델
- 기본: `weights/whisper-small-elderly-v1/` (노인 음성으로 파인튜닝한 Whisper small, faster-whisper int8) — 있으면 자동으로 사용
- 없으면 원본 Whisper small 을 시작할 때 내려받아 씀 (464MB, 느림)
- 학습 기록: 노션 "모델 실험 기록" `whisper-small-elderly-v1` (CER 9.44% → 3.75%)

## 배포(이미지 빌드) 순서
모델 파일(약 250MB)은 Git 에 없고 GitHub Release 에 있습니다. **빌드 전에 꼭 받으세요.**
```
bash model/scripts/fetch_model.sh          # → model/weights/whisper-small-elderly-v1/ (gh 로그인 필요)
docker compose build model                 # Dockerfile 의 COPY weights 로 이미지 안에 들어감 (약 1.3GB)
```
- CPU 4개 이상, 메모리 2~3GB 권장. CPU 4코어에서 문장당 약 1.8초 (메뉴 힌트 켜면 약 +0.5초)
- 모델 불러오기는 약 1초. readinessProbe 는 `GET /ready`

## 환경변수
| 이름 | 기본값 | 설명 |
|---|---|---|
| `WHISPER_MODEL` | (위 기본 모델) | 다른 모델 폴더 경로나 `small`. 원본으로 되돌릴 때 `small` |
| `STT_MENU_HINTS` | `1` | 요청에 `hints` 가 없으면 백엔드 메뉴 이름을 힌트로 씀. `0` = 끔 |
| `BACKEND_URL` | `http://backend:8000` | 메뉴 이름을 가져올 백엔드 주소 (쿠버네티스 Service 이름이 다르면 지정) |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | `cpu` / `int8` | GPU 면 `cuda` / `float16` |

## 다시 학습하기
1. 내 컴퓨터(한국 IP)에서 데이터 준비: `model/scripts/prepare_aihub.py` (AI Hub 는 해외 IP 차단 → Colab 에서 직접 못 받음)
2. Colab 학습: `model/notebooks/whisper_finetune_colab.ipynb`
3. 결과 zip 을 새 Release 로 올리고 `fetch_model.sh` 의 기본 태그를 바꿈
