# 노션 위치 정보 (AI가 읽는 파일)

노션 워크스페이스: Fundamental 1 project (팀스페이스 안의 "Fundamental 1 project" 페이지가 홈)
노션 도구로 아래 URL/ID를 fetch 하거나, 이름으로 search 해서 찾는다.

| 이름 | 용도 | 페이지 URL | 데이터 소스 |
|---|---|---|---|
| 프로젝트 홈 | 전체 목차 | https://app.notion.com/p/3fb4c378882381178dc9f732fd1d2cff | - |
| 작업 로그 | 작업 기록 (wrap-up이 작성, catch-up이 읽음) | https://app.notion.com/p/ab9d88dffd0a4537be3cce00b0d701d7 | collection://d9f6f0c5-1132-4c61-b6eb-5aa52f1e6ab1 |
| 할 일 보드 | 파트별 할 일 | https://app.notion.com/p/ad687942cd4a4984854d2d794f7983d0 | collection://a79c13ed-8f7f-4a13-b33a-3f4880dc9510 |
| 회의록 | 회의 결정 사항 | https://app.notion.com/p/82a347a15dfc43ed82a87973bb72f605 | collection://88107937-e4f8-48b4-bb51-ed9232761aa6 |
| 모델 실험 기록 | 모델 실험 결과 | https://app.notion.com/p/46cc3b8a44f841c7b6b50486f036a5dc | collection://22429e9c-6523-4848-82ae-420e3bbf4c52 |
| API 명세 | 파트 간 API·모델 입출력 약속 | https://app.notion.com/p/3fb4c378882381f59122fb25e293b710 | - |
| 기획서 | 기능 명세 | https://app.notion.com/p/3fb4c3788823815083a2c071cb6feca1 | - |
| 역할 분담 | 역할별 책임 | https://app.notion.com/p/3fb4c378882381ec91dcf2913da3888e | - |

## 작업 로그 속성
- 작업 (제목): 한 줄 요약. 예) "[백엔드] 로그인 API 추가"
- 날짜: 오늘 날짜
- 작성자: 노션 사용자 (노션 도구의 "내 정보(get-self)"로 얻은 user id)
- 파트: PM / 기획 / 백엔드 / 프론트엔드 / 모델 구축 / 공통 / 배포
- AI 도구: Claude Code / Codex / 직접
- 상태: 진행 중 / PR 대기 / Merge 완료 / 막힘
- 브랜치, PR(URL), 커밋(짧은 해시 목록), 다음 할 일, 다른 파트 영향

## 할 일 보드 속성
- 작업(제목), 상태(할 일 / 진행 중 / 리뷰 / 완료), 파트(PM / 기획 / 백엔드 / 프론트엔드 / 모델 구축 / 공통), 담당자, 우선순위, 마감일, 마일스톤, 메모
