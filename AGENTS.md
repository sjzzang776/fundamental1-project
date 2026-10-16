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
- PR은 최소 1명이 확인한 뒤 Merge합니다.
- `.env`, 데이터셋, 모델 가중치 파일(*.pt 등)은 커밋하지 않습니다. 큰 파일은 Google Drive 등에 올리고 노션 "자료실"에 링크를 남깁니다.
