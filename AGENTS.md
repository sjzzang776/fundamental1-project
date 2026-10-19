# Fundamental 1 project · 팀 규칙

이 저장소의 팀원 대부분은 비전공자입니다. AI 에이전트는 한국어로, 쉬운 말로 설명하고,
명령을 실행하기 전에 무엇을 하는지 먼저 알려주세요.

## 구조와 담당
| 폴더 | 담당 | 내용 |
|---|---|---|
| frontend/ | 프론트엔드 | React + Vite, 배포 시 Nginx |
| backend/ | 백엔드 | FastAPI, PostgreSQL |
| model/ | 모델 구축 | 학습 코드, 추론 API (/predict) |
| docs/ | 기획 · PM | 기획 문서 (주 문서는 노션) |
| docker-compose*.yml, k8s/ | 백엔드(배포 담당) | 통합 실행과 배포 |

- 자기 파트 폴더만 수정합니다. 다른 파트 폴더를 고쳐야 하면 PR 설명에 적고 해당 담당자에게 리뷰를 받습니다.
- 파트 간 약속(API 주소·요청/응답 형식, 모델 입출력 형식)을 바꾸면 노션 "API 명세" 페이지도 함께 고칩니다.

## 실행 방법 (Docker Desktop 실행 후)
- 처음 한 번: `.env.example` 을 복사해 `.env` 만들기
- 전체 통합 실행: `docker compose up --build` → http://localhost:3000
- 개발 모드(코드 저장 즉시 반영): `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build <서비스>`
  - 프론트엔드: `frontend-dev` → http://localhost:5173
  - 백엔드: `backend` → http://localhost:8000/docs
  - 모델: `model` → http://localhost:8001/docs
- 종료: `docker compose down` (DB 데이터까지 지우려면 `docker compose down -v`)
- 라이브러리를 추가했다면(`requirements.txt`, `package.json` 수정) `--build` 를 붙여 다시 실행합니다.

## Git 규칙
- `main` 에 직접 push하지 않습니다. 항상 브랜치를 만들고 PR을 올립니다.
- 브랜치 이름: `feat/<파트>-<내용>`, `fix/<파트>-<내용>` (예: `feat/backend-login`, `fix/frontend-button`)
  - 파트: `pm`, `plan`, `frontend`, `backend`, `model`, `infra`
- 커밋 메시지: `[파트] 한 일` (예: `[모델] 감성 분류 모델 v1 추가`)
- 작업 시작 전 `git switch main && git pull` 로 최신화합니다.
- PR은 wrap-up 절차의 실행 확인(내 컴퓨터 + GitHub CI "Docker 실행 확인")을 통과하면 AI가 자동으로 Merge합니다. CI가 실패한 PR은 Merge하지 않습니다. 리뷰 의견은 Merge 후에도 PR에 남길 수 있습니다.
- PR 본문은 노션 작업 로그로 자동 옮겨지므로 `.github/pull_request_template.md` 의 섹션을 모두 채웁니다. PR 제목은 `[파트] 한 일` 형식입니다.
- `.env`, 데이터셋, 모델 가중치 파일(*.pt 등)은 커밋하지 않습니다. 큰 파일은 Google Drive 등에 올리고 노션 "자료실"에 링크를 남깁니다.

## AI 작업 루틴 (Claude Code · Codex 공통)
- **작업 시작:** 사용자가 작업을 시작하거나 "이어서 하자", "뭐 바뀌었어?", "catch-up" 이라고 하면 `docs/ai/catch-up.md` 절차를 따른다. 새 세션의 첫 요청이 코드 작업이면, 시작 전에 catch-up을 먼저 할지 한 번 묻는다.
- **작업 마무리:** 사용자가 "작업 끝", "마무리", "올려줘", "wrap-up" 이라고 하면 `docs/ai/wrap-up.md` 절차를 따른다.
- 요청받은 작업을 끝냈다고 판단되면, 마지막 답변에서 **"마무리(wrap-up)할까요? GitHub에 올려 main에 합치고 노션 작업 로그를 남깁니다."** 라고 묻는다. 사용자가 동의하면 wrap-up을 끝까지 자동으로 진행한다 (push, PR, 충돌 해결, Merge 포함).
- Merge 충돌은 AI가 양쪽 변경 의도를 확인해 둘 다 살리는 방향으로 해결한다. 둘 다 살릴 수 없을 때만 사용자에게 묻는다 (`docs/ai/wrap-up.md` 3단계).
- 노션 위치 정보: `docs/ai/notion.md`
- 내 파트는 `git config --get fundamental1.part` 에 저장되어 있다 (없으면 물어서 저장).

## 정보가 필요할 때 (모든 작업 공통)
- 진행은 채팅으로 한다. 한 번에 질문 하나, 무엇이 왜 필요한지와 어디서 찾는지를 함께 알려준다.
- **일반 정보**(이름, 아이디, 주소, 선택지 등)는 채팅으로 받는다.
- **민감 정보**(비밀번호, 토큰, API 키)는 채팅으로 받지 않는다. 해당 파일(`.env` 등, Git에 안 올라가는 파일)에 `여기에-입력` 자리표시자를 넣어 두고,
  "🔒 민감한 정보라 채팅에 쓰지 말아 주세요. `<파일 경로>` 의 `<N>`번째 줄 `KEY=여기에-입력` 을 바꾸고 저장한 뒤 '수정했어'라고 알려주세요. 확인해 보겠습니다." 라고 안내한다.
  "수정했어"라고 하면 자리표시자가 사라졌는지·형식이 맞는지·동작하는지 확인하되, 값은 화면에 출력하지 않는다. 새 환경변수를 추가했다면 `.env.example` 에도 키 이름만 추가한다.
- **로그인·승인**은 사용자가 브라우저나 별도 터미널에서 직접 하게 하고, "완료"라고 하면 확인 명령으로 검증한다.
