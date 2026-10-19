# 배포 기록 (GKE · https://8-232-203-94.sslip.io)

배포할 때마다 맨 위에 한 줄씩 추가합니다. **문제가 생기면 "되돌리기" 칸의 명령을 그대로 실행**하면 됩니다.
이미지 태그 = 그 버전의 main 커밋. 예전 태그 이미지는 이미지 보관함(Artifact Registry)에서 지우지 않습니다.

| # | 날짜 (KST) | 배포한 사람 | 태그 (커밋) | 바뀐 것 | 확인 결과 | 되돌리기 |
|---|---|---|---|---|---|---|
| 2 | 2026-10-19 22:10 | 세진 (Claude Code) | `2824c6e` | 의도 파악 모델 2개(#24·#28·#30), 버튼 눌러 말하기(#27), 백엔드 음성 주문 개선(#19), 배포 설정(#29·#31) · 모델 서버 CPU 2→8, 메모리 3→8Gi (새 노드 자동 추가) | `/api/health` ok · 모델 `/health` stt·nlu_intent·nlu_gen 모두 true · "봉투에 담아 줘"→포장, "그 매운 닭 버거 두 개"→맥스파이시 상하이 버거 2개(1.7초) · 주문 확인까지 정상 · DB 재시작 없음 | `bash scripts/rollback.sh 253dc8f` |
| 1 | 2026-10-19 | 길버트 | `253dc8f` | 첫 배포: 화면·백엔드·음성 인식(whisper-small-elderly-v1)·DB, https 주소 (#29) | `/api/health` ok, 인증서 Active | (처음 배포) |

## 되돌리기
```bash
bash scripts/rollback.sh <태그>   # 예: 253dc8f → 화면·백엔드·모델 서버 이미지를 그 버전으로
bash scripts/rollback.sh          # 바로 전 버전으로 (kubectl rollout undo)
```
- 모델 서버 CPU·메모리까지 예전으로: 백업의 `all.yaml` 에서 model 의 `resources` 를 보고 `k8s/model.yaml` 을 고쳐 `kubectl apply -k k8s`
- 되돌린 뒤에도 이 표에 한 줄 남겨 주세요 (바뀐 것: "되돌림 → 253dc8f").

## 배포 전 백업 (배포한 사람 PC, Git 에 올리지 않음: DB 에 주문 기록이 있음)
| # | 위치 | 내용 |
|---|---|---|
| 2 | 세진 PC `Documents\프로젝트1\deploy-backups\20261019-2146-before\` | `all.yaml`(배포 설정 전체) · `images.txt`(이미지 태그) · `db.sql`(DB 전체, UTF-8) |

## DB 되돌리기 (필요할 때만, 주문 기록이 백업 시점으로 돌아감)
```bash
kubectl -n fundamental1 exec -i postgres-0 -- sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
kubectl -n fundamental1 exec -i postgres-0 -- sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < deploy-backups/<폴더>/db.sql
kubectl -n fundamental1 rollout restart deployment/backend
```
