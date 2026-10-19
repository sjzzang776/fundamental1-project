# Fundamental 1 project

> 한 줄 소개: (기획 확정 후 작성)

웹 서비스(프론트엔드 · 백엔드)와 AI 모델을 함께 만드는 팀 프로젝트입니다.
팀 문서, 할 일, 회의록, 작업 로그는 노션 "Fundamental 1 project" 워크스페이스에서 관리합니다.

## 기술 스택
| 파트 | 폴더 | 기술 | 포트 |
|---|---|---|---|
| 프론트엔드 | `frontend/` | React + Vite, 배포 시 Nginx | 3000 (개발 서버 5173) |
| 백엔드 | `backend/` | Python 3.12 + FastAPI | 8000 |
| 모델 구축 | `model/` | Python 3.12 + FastAPI 추론 서버 | 8001 |
| DB | - | PostgreSQL 16 | 5432 |

요청 흐름: `브라우저 → frontend(Nginx) → /api/* → backend → model`, backend는 DB도 사용합니다.

## 실행 방법
사전 준비: [Docker Desktop](https://www.docker.com/products/docker-desktop/)을 설치하고 실행해 둡니다.

1. 처음 한 번: `.env.example` 을 복사해 `.env` 를 만들고 `POSTGRES_PASSWORD` 를 바꿉니다.
2. 전체 실행: `docker compose up --build` → http://localhost:3000
3. 내 파트만 개발 모드로 실행 (코드 저장 즉시 반영):

   | 파트 | 명령 | 주소 |
   |---|---|---|
   | 프론트엔드 | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build frontend-dev` | http://localhost:5173 |
   | 백엔드 | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build backend` | http://localhost:8000/docs |
   | 모델 | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build model` | http://localhost:8001/docs |

4. 종료: `docker compose down`

## 폴더 구조
```
├─ frontend/   React 화면 (Nginx로 배포)
├─ backend/    FastAPI 서버 (/api/*)
├─ model/      모델 추론 서버(/predict), 학습 노트북, 데이터·가중치(Git 제외)
├─ docs/       기획 · PM 문서
├─ docker-compose.yml       전체 통합 실행
└─ docker-compose.dev.yml   개발 모드
```

협업 규칙은 [AGENTS.md](AGENTS.md)를 참고하세요.
