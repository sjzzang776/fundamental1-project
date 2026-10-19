"""PR 이벤트를 받아 노션 '작업 로그' 데이터베이스에 기록한다. (GitHub Actions에서 실행)

- PR이 열리면 상태 "PR 대기"로 새 항목을 만들고, Merge되면 같은 항목을 "Merge 완료"로 바꾼다.
- 본문은 PR 본문을 그대로 옮긴다. 그래서 PR 본문은 .github/pull_request_template.md 의 섹션을 모두 채운다.
- 외부 라이브러리 없이 표준 라이브러리만 쓴다.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
KST = timezone(timedelta(hours=9))
TEXT_LIMIT = 2000  # 노션 텍스트 한 덩어리 최대 길이
BLOCK_LIMIT = 100  # 한 번에 만들 수 있는 블록 수

PART_BY_TAG = {
    "PM": "PM",
    "기획": "기획",
    "백엔드": "백엔드",
    "프론트": "프론트엔드",
    "프론트엔드": "프론트엔드",
    "모델": "모델 구축",
    "모델 구축": "모델 구축",
    "공통": "공통",
    "배포": "배포",
}


def notion(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"::error::노션 API 오류 {e.code}: {detail}")
        if e.code in (401, 403, 404):
            print("::error::NOTION_TOKEN 이 맞는지, 노션 '작업 로그' 페이지에 통합(연결)을 추가했는지 확인하세요.")
        sys.exit(1)


def rich(text):
    return [{"text": {"content": text[:TEXT_LIMIT]}}] if text else []


def sections(body):
    """'## 제목' 단위로 PR 본문을 나눈다."""
    result, current = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            result[current] = []
        elif current is not None:
            result[current].append(line)
    return {k: "\n".join(v).strip() for k, v in result.items()}


def find_section(secs, *keywords):
    for title, text in secs.items():
        if any(k in title for k in keywords):
            return text
    return ""


def clean(line):
    return line.replace("**", "").strip()


def flat(text):
    """속성 칸에 넣을 수 있게 목록 기호를 정리한다."""
    text = re.sub(r"^\s*- \[( |x|X)\]\s*", "• ", text, flags=re.M)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.M)
    return clean(text)


def to_blocks(body):
    blocks = []
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("<!--"):
            continue
        if line.startswith("## "):
            blocks.append({"heading_2": {"rich_text": rich(clean(line[3:]))}})
        elif line.startswith("### "):
            blocks.append({"heading_3": {"rich_text": rich(clean(line[4:]))}})
        elif re.match(r"^\s*- \[( |x|X)\] ", line):
            done = re.match(r"^\s*- \[(x|X)\] ", line) is not None
            text = re.sub(r"^\s*- \[( |x|X)\] ", "", line)
            blocks.append({"to_do": {"rich_text": rich(clean(text)), "checked": done}})
        elif re.match(r"^\s*[-*] ", line):
            blocks.append({"bulleted_list_item": {"rich_text": rich(clean(re.sub(r"^\s*[-*] ", "", line)))}})
        else:
            blocks.append({"paragraph": {"rich_text": rich(clean(line))}})
    return blocks[:BLOCK_LIMIT]


def main():
    if not os.environ.get("NOTION_TOKEN"):
        print("::warning::NOTION_TOKEN 시크릿이 없어 노션 기록을 건너뜁니다.")
        return

    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        event = json.load(f)
    pr = event["pull_request"]
    merged = event["action"] == "closed" and pr.get("merged")
    if event["action"] == "closed" and not merged:
        return

    db = os.environ["NOTION_DATABASE_ID"]
    title = pr["title"]
    body = pr.get("body") or ""
    secs = sections(body)

    tag = re.match(r"\s*\[([^\]]+)\]", title)
    part = PART_BY_TAG.get(tag.group(1).strip()) if tag else None

    with open(".github/notion-team.json", encoding="utf-8") as f:
        team = json.load(f)
    author_id = team.get(pr["user"]["login"])

    tool_text = find_section(secs, "AI 도구") or body
    if "Codex" in tool_text:
        tool = "Codex"
    elif "Claude" in tool_text:
        tool = "Claude Code"
    else:
        tool = "직접"

    when = pr["merged_at"] if merged else pr["created_at"]
    date = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(KST).date().isoformat()
    commit = (pr["merge_commit_sha"] if merged else pr["head"]["sha"])[:7]

    props = {
        "작업": {"title": rich(title)},
        "날짜": {"date": {"start": date}},
        "상태": {"select": {"name": "Merge 완료" if merged else "PR 대기"}},
        "AI 도구": {"select": {"name": tool}},
        "브랜치": {"rich_text": rich(pr["head"]["ref"])},
        "PR": {"url": pr["html_url"]},
        "커밋": {"rich_text": rich(commit)},
        "다음 할 일": {"rich_text": rich(flat(find_section(secs, "다음 할 일")))},
        "다른 파트 영향": {"rich_text": rich(flat(find_section(secs, "다른 파트")))},
    }
    if part:
        props["파트"] = {"select": {"name": part}}
    if author_id:
        props["작성자"] = {"people": [{"id": author_id}]}

    found = notion("POST", f"/databases/{db}/query",
                   {"filter": {"property": "PR", "url": {"equals": pr["html_url"]}}})["results"]
    if found:
        page = notion("PATCH", f"/pages/{found[0]['id']}", {"properties": props})
        print(f"노션 작업 로그 갱신: {page['url']}")
    else:
        page = notion("POST", "/pages", {
            "parent": {"database_id": db},
            "properties": props,
            "children": to_blocks(body),
        })
        print(f"노션 작업 로그 작성: {page['url']}")


if __name__ == "__main__":
    main()
