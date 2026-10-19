# 배포 기록 (GKE · https://8-232-203-94.sslip.io)

배포할 때마다 맨 위에 한 줄씩 추가합니다. **문제가 생기면 "되돌리기" 칸의 명령을 그대로 실행**하면 됩니다.
이미지 태그 = 그 버전의 main 커밋. 예전 태그 이미지는 이미지 보관함(Artifact Registry)에서 지우지 않습니다.

| # | 날짜 (KST) | 배포한 사람 | 태그 (커밋) | 바뀐 것 | 확인 결과 | 되돌리기 |
|---|---|---|---|---|---|---|
| 9 | 2026-10-20 01:55 | 세진 (Claude Code) | 화면·백엔드·모델 모두 `e5fe090` | 음성 인식 개선(#42): 화면별 힌트(63문장 79→97%) · 말로 화면 조작(쪽 넘기기·메뉴판·다시 듣기) · 분석용 녹음 저장 켬(`STT_DEBUG_DIR=/tmp/stt-debug`, 최근 200개, 모델 Pod 를 다시 켜면 지워짐) | 모델 `/health` stt·nlu_intent·nlu_gen true · 화면에 next_page·show_menu 처리 들어감 | 첫 배포 시험 상태로: `bash scripts/rollback.sh 253dc8f` / 7차 상태로: DEPLOY_LOG "시험 끝나고 돌아가기" |
| 8 | 2026-10-20 01:25 | 세진 (Claude Code) | 화면·백엔드·모델 모두 `253dc8f` (시험용 되돌림) | PM 요청: 음성 인식률 비교를 위해 길버트 킴 님 첫 배포 버전으로 잠시 되돌림. 브랜치 `test/first-deploy-253dc8f`. 사람 목소리·의도 파악 모델 없음 | 모델 `/health` whisper-small-elderly-v1 · stt_ready true · 화면 에코 제거 켜짐(그때 설정) | **최신으로 돌아가기:** 화면 `9fa5291` · 백엔드 `fb5f31f` · 모델 `9144a34` (아래 "시험 끝나고 돌아가기") |
| 7 | 2026-10-20 00:45 | 세진 (Claude Code) | 화면 `9fa5291` · 백엔드 `fb5f31f` · 모델 `9144a34` | 음성 인식이 말소리 없는 녹음에서 메뉴 힌트를 그대로 읽던 문제 막기(#39) · 생성 모델 스레드 8→6 | 모델 `/health` 정상 · 생성 모델 0.5~0.7초 (스레드 8 일 때 1.7초) · 잡음만 있는 녹음 → 빈 결과 | 모델 `kubectl -n fundamental1 set image deployment/model model=<보관함>/model:2824c6e` |
| 6 | 2026-10-20 00:00 | 세진 (Claude Code) | 화면 `9fa5291` | 말 첫소리 잘림 수정(#38): 시작 감지 완화 + 1초 앞부터 보내기 | 첫소리 잘림 재현 시험(앞 0.04~0.08초 잘림 = 같은 오류) · 수정 뒤 "먹고 간다고" "세트로 줘" 등 정상 인식 | 화면 `9329e49` 로 |
| 5 | 2026-10-19 23:30 | 세진 (Claude Code) | 화면 `9329e49` | 마이크 에코 제거 끄기(#37): 사람 목소리 안내 중 끼어들기 안 되던 문제 | 배포 화면 코드에 echoCancellation 꺼짐 확인 | 화면 `fb5f31f` 로 |
| 4 | 2026-10-19 23:10 | 세진 (Claude Code) | 화면·백엔드 `fb5f31f` · 모델 `2824c6e` | 말하면 바로 알아듣기 다시 기본으로(#27 되돌림), 안내 목소리 빠르기 1.1·쉼표 안 쉼·문장 이어 붙이기 (#35). 모델 서버는 그대로 (다시 켜지 않음) | `/api/health` ok · 화면에 "말씀하시면 바로 들어요" · 인사말 음성 0.1초, 2문장 0.75초 | `bash scripts/rollback.sh 8e75bc7` 후 모델만 `2824c6e` 로 (아래 메모) |
| 3 | 2026-10-19 22:40 | 세진 (Claude Code) | 화면·백엔드 `8e75bc7` · 모델 `2824c6e` | 안내 음성을 사람 목소리로 (Google TTS Chirp 3 HD, #33). 키는 Secret `tts-secret` · 모델 서버는 코드 변경이 없어 `2824c6e` 유지 (새 모델 Pod 가 GCP 전체 CPU 할당량 32 초과로 Pending → 같은 코드인 이전 태그로 되돌림, `k8s/model.yaml` 교체 방식 수정) | `/api/tts` 미리 만든 문장 0.05~0.09초 · 새 문장 0.67초 · 같은 문장 다시 0.07초 · `/api/health` ok | `bash scripts/rollback.sh 2824c6e` |
| 2 | 2026-10-19 22:10 | 세진 (Claude Code) | `2824c6e` | 의도 파악 모델 2개(#24·#28·#30), 버튼 눌러 말하기(#27), 백엔드 음성 주문 개선(#19), 배포 설정(#29·#31) · 모델 서버 CPU 2→8, 메모리 3→8Gi (새 노드 자동 추가) | `/api/health` ok · 모델 `/health` stt·nlu_intent·nlu_gen 모두 true · "봉투에 담아 줘"→포장, "그 매운 닭 버거 두 개"→맥스파이시 상하이 버거 2개(1.7초) · 주문 확인까지 정상 · DB 재시작 없음 | `bash scripts/rollback.sh 253dc8f` |
| 1 | 2026-10-19 | 길버트 | `253dc8f` | 첫 배포: 화면·백엔드·음성 인식(whisper-small-elderly-v1)·DB, https 주소 (#29) | `/api/health` ok, 인증서 Active | (처음 배포) |

## 시험 끝나고 돌아가기 (8차 → 7차 상태)
```bash
R=asia-northeast3-docker.pkg.dev/project-b10d899d-6de4-4ec8-a03/fundamental1
kubectl -n fundamental1 set image deployment/frontend frontend=$R/frontend:9fa5291
kubectl -n fundamental1 set image deployment/backend backend=$R/backend:fb5f31f
kubectl -n fundamental1 set image deployment/model model=$R/model:9144a34
```

## 분석용 녹음 꺼내기 (9차부터 켜 둠)
```bash
kubectl -n fundamental1 cp $(kubectl -n fundamental1 get pod -l app=model -o name | head -1 | cut -d/ -f2):/tmp/stt-debug ./stt-debug
```
끄기: `kubectl -n fundamental1 set env deployment/model STT_DEBUG_DIR-`

## 되돌리기
- 화면·백엔드와 모델 서버 태그가 다를 때(4차부터): `kubectl -n fundamental1 set image deployment/frontend frontend=<보관함>/frontend:<태그>` 처럼 하나씩 되돌릴 수 있음. 보관함 = `asia-northeast3-docker.pkg.dev/project-b10d899d-6de4-4ec8-a03/fundamental1`
```bash
bash scripts/rollback.sh <태그>   # 예: 253dc8f → 화면·백엔드·모델 서버 이미지를 그 버전으로
bash scripts/rollback.sh          # 바로 전 버전으로 (kubectl rollout undo)
```
- 모델 서버 CPU·메모리까지 예전으로: 백업의 `all.yaml` 에서 model 의 `resources` 를 보고 `k8s/model.yaml` 을 고쳐 `kubectl apply -k k8s`
- 되돌린 뒤에도 이 표에 한 줄 남겨 주세요 (바뀐 것: "되돌림 → 253dc8f").

## 배포 전 백업 (배포한 사람 PC, Git 에 올리지 않음: DB 에 주문 기록이 있음)
| # | 위치 | 내용 |
|---|---|---|
| 9 | 세진 PC `Documents\프로젝트1\deploy-backups\20261020-0150-before-stt-hints\` | 8차 상태 (모두 `253dc8f`) |
| 8 | 세진 PC `Documents\프로젝트1\deploy-backups\20261020-0120-before-test-253dc8f\` | 7차 상태 (화면 `9fa5291`, 백엔드 `fb5f31f`, 모델 `9144a34`) |
| 7 | 세진 PC `Documents\프로젝트1\deploy-backups\20261020-0042-before-stt-guard\` | 같은 구성 (배포 전: 화면 `9fa5291`, 백엔드 `fb5f31f`, 모델 `2824c6e`) |
| 4 | 세진 PC `Documents\프로젝트1\deploy-backups\20261019-2307-before-handsfree\` | 같은 구성 (배포 전: 화면·백엔드 `8e75bc7`, 모델 `2824c6e`) |
| 3 | 세진 PC `Documents\프로젝트1\deploy-backups\20261019-2226-before-tts\` | 같은 구성 (배포 전 태그 `2824c6e`) |
| 2 | 세진 PC `Documents\프로젝트1\deploy-backups\20261019-2146-before\` | `all.yaml`(배포 설정 전체) · `images.txt`(이미지 태그) · `db.sql`(DB 전체, UTF-8) |

## DB 되돌리기 (필요할 때만, 주문 기록이 백업 시점으로 돌아감)
```bash
kubectl -n fundamental1 exec -i postgres-0 -- sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
kubectl -n fundamental1 exec -i postgres-0 -- sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < deploy-backups/<폴더>/db.sql
kubectl -n fundamental1 rollout restart deployment/backend
```
