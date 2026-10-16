# catch-up: 작업 이어받기 절차

목표: 사용자가 자리를 비운 사이 GitHub와 노션에서 무엇이 바뀌었는지 파악하고, 이어서 할 일을 정한다.
사용자는 비전공자다. 한국어로 쉽게, 짧게 요약한다. 이 절차는 읽기만 하고 아무것도 바꾸지 않는다 (마지막에 묻고 나서만 pull 등 실행).

## 0. 내 파트 확인
- `git config --get fundamental1.part` 로 저장된 파트를 확인한다.
- 없으면 사용자에게 파트를 묻고 저장한다: `git config fundamental1.part <pm|plan|frontend|backend|model|infra>`
  (이 설정은 내 컴퓨터에만 저장되고 GitHub에 올라가지 않는다)

## 1. GitHub 확인
1. `git fetch --all --prune`
2. 현재 상태: `git status -sb` (현재 브랜치, 커밋 안 한 변경, main보다 뒤처졌는지)
3. main의 최근 변화:
   - `git log origin/main --since="7 days ago" --pretty=format:"%h | %an | %ar | %s"` (없으면 `-15`)
   - 마지막으로 내가 받은 이후 바뀐 폴더: `git diff --stat HEAD...origin/main`
4. PR:
   - 열린 PR: `gh pr list --state open`
   - 최근 Merge된 PR: `gh pr list --state merged --limit 10`
   - 내 브랜치의 PR 상태: `gh pr view --json number,state,reviewDecision,url` (없으면 건너뜀)
   - 나에게 요청된 리뷰: `gh pr list --search "review-requested:@me"`

## 2. 노션 확인 (docs/ai/notion.md 의 위치 사용)
1. **작업 로그**: 최근 항목 10개를 날짜 최신순으로 본다. 특히
   - 내 파트 항목의 "다음 할 일"과 본문의 "다음 작업자를 위한 메모"
   - 다른 파트 항목의 "다른 파트 영향" (내 파트에 영향이 있는지)
   - 상태가 "PR 대기"인 내 항목 → 1단계의 PR이 Merge되었으면 "Merge 완료"로 바꿀지 마지막에 묻는다
2. **할 일 보드**: 내 파트에서 상태가 "할 일" 또는 "진행 중"인 항목, 마감일이 가까운 항목
3. **API 명세**: 최근 수정되었는지, 변경 이력에 새 항목이 있는지
4. **회의록**: 최근 회의의 "결정 사항"
- **노션 도구가 연결되어 있지 않아도 된다.** 작업 로그는 PR 본문을 옮긴 것이므로, 같은 내용을 GitHub에서 읽는다:
  `gh pr list --state merged --limit 10 --json number,title,author,mergedAt,body`
  `gh pr list --state open --json number,title,author,body`
  각 PR 본문의 "다음 할 일", "다른 파트에 영향", "다음 작업자를 위한 메모" 섹션을 위 1번과 같은 기준으로 본다.
  할 일 보드·API 명세·회의록은 노션 연결이 있어야 읽을 수 있으므로, 연결이 없으면 "할 일 보드는 노션에서 직접 확인해 주세요"라고 안내한다.

## 3. 요약 보고 (이 형식으로)
### 📌 그동안 바뀐 것
- 팀 전체: (main에 들어온 변경을 파트별로 1줄씩)
- 노션: (새 작업 로그, 회의 결정, API 명세 변경)
### ⚠️ 내 파트에 영향 있는 것
- (예: 백엔드가 /api/predict 응답 형식을 바꿈 → 프론트 수정 필요)
### 🧭 내 상태
- 현재 브랜치, 커밋 안 한 변경, main보다 몇 커밋 뒤처졌는지, 내 PR 상태
### ✅ 이어서 할 일 추천 (최대 3개)
1. (작업 로그의 "다음 할 일"과 할 일 보드 기준, 이유 한 줄)

## 4. 다음 행동 묻기
- main보다 뒤처졌으면 최신화를 제안한다:
  - main에 있다면 `git pull`
  - 작업 브랜치에 있다면 `git merge origin/main` (충돌이 나면 쉬운 말로 설명하고 함께 해결)
- 커밋 안 한 변경이 있는데 다른 일을 하려 하면, 먼저 wrap-up 하거나 `git stash` 할지 묻는다.
- 사용자가 할 일을 고르면, 해당 할 일 보드 항목을 "진행 중"으로 바꿀지 묻고, main에서 새 브랜치 `feat/<파트>-<내용>` 을 만든 뒤 작업을 시작한다.
