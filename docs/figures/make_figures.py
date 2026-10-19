"""README 그림을 코드로 그린다 (발표 자료 이미지를 쓰지 않음).

    python docs/figures/make_figures.py      # 저장소 맨 위에서 실행 (Edge 또는 Chrome 필요) → docs/img/*.png

  fig_architecture.png   서비스 구조: 손님 화면 → 백엔드 → 모델 서버 · DB, 배포 (k8s/, docker-compose.yml 기준)
  fig_understanding.png  손님 말을 알아듣는 순서: 규칙 → 분류 모델 → 생성 모델 → Claude (backend/app/services/nlu.py, model/app/main.py 기준)
  fig_results.png        모델 성능 수치 (GitHub Release 기록 기준)
스타일·렌더러: figstyle.py · 로고: Simple Icons 13.21.0 (CC0-1.0), 각 로고는 상표권자 소유
"""
import re
from pathlib import Path

from figstyle import page, render

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "img"
ICONS = HERE / "icons"
BRAND = {"react": "#087EA4", "vite": "#646CFF", "nginx": "#009639", "fastapi": "#009688", "postgresql": "#4169E1",
         "sqlalchemy": "#D71F00", "python": "#3776AB", "docker": "#2496ED", "kubernetes": "#326CE5",
         "googlecloud": "#4285F4", "githubactions": "#2088FF", "notion": "#000000", "huggingface": "#FFB000",
         "onnx": "#005CED", "anthropic": "#191919", "pytorch": "#EE4C2C"}
INK, SUB, LINE, BLUE = "#14202B", "#5A6876", "#9AA6B2", "#2B50E0"


def logo(name, cx, cy, size):
    d = re.search(r'<path d="([^"]+)"', (ICONS / f"{name}.svg").read_text(encoding="utf-8")).group(1)
    k = size / 24
    return f'<path d="{d}" fill="{BRAND[name]}" transform="translate({cx - size/2:.1f},{cy - size/2:.1f}) scale({k:.4f})"/>'


def marker(color):
    return (f'<marker id="a{color[1:]}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>')


def tile(cx, cy, s, inner, hi=False):
    fill, stroke, sw = ("#E8EDFD", BLUE, 2.4) if hi else ("#FFFFFF", "#D3DAE1", 1.4)
    return f'<rect x="{cx-s/2}" y="{cy-s/2}" width="{s}" height="{s}" rx="{s*.24:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>' + inner


def emoji(ch, cx, cy, size):
    return f'<text x="{cx}" y="{cy + size*0.36}" text-anchor="middle" font-size="{size}">{ch}</text>'


def label(cx, y, title, lines=(), color=INK):
    s = f'<text x="{cx}" y="{y}" text-anchor="middle" font-size="15.5" font-weight="700" fill="{color}">{title}</text>'
    for k, ln in enumerate(lines):
        s += f'<text x="{cx}" y="{y + 20 + k*17}" text-anchor="middle" font-size="12.5" fill="{SUB}">{ln}</text>'
    return s


def wire(x1, y1, x2, y2, text="", color=LINE, mid=None, dash=""):
    mx = (x1 + x2) / 2
    path = f"M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" if y1 != y2 else f"M{x1},{y1} L{x2},{y2}"
    s = f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.2" marker-end="url(#a{color[1:]})"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>"
    if text:
        lx, ly = mid or (mx, min(y1, y2) - 9)
        s += f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="12" fill="{SUB}">{text}</text>'
    return s


def frame(title, lede, svg, w):
    return page(f'<div class="frame"><div class="title">{title}</div><div class="lede">{lede}</div>{svg}</div>', w)


# ------------------------------------------------------------------ 1. 구조도
def fig_architecture():
    W, H = 1180, 560
    defs = "".join(marker(c) for c in (LINE, BLUE))
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs>{defs}</defs>']
    # GKE 영역
    s.append('<rect x="210" y="150" width="950" height="250" rx="18" fill="#F7F9FB" stroke="#C9D2DA" stroke-width="1.4"/>')
    s.append(logo("kubernetes", 240, 176, 22) + logo("googlecloud", 268, 176, 22))
    s.append(f'<text x="288" y="181" font-size="13.5" font-weight="700" fill="{SUB}">GCP 쿠버네티스(GKE Autopilot, 서울) · https 주소 · 같은 구성을 docker compose 로도 실행</text>')
    y, T = 285, 76
    # 손님
    s.append(tile(110, y, T, emoji("👵", 110, y, 40)))
    s.append(label(110, y + T/2 + 24, "손님 (휴대폰·키오스크)", ["말하기 · 버튼 누르기"]))
    nodes = [
        (330, [("react", -13), ("vite", 15)], "화면 frontend/", ["React + Vite, Nginx", "녹음·말 시작 감지·재생"], True),
        (590, [("fastapi", -13), ("sqlalchemy", 15)], "백엔드 backend/", ["주문 대화 단계 관리", "말 이해 규칙 · 장바구니"], True),
        (850, [("python", -13), ("pytorch", 15)], "모델 서버 model/", ["음성 인식 /stt", "의도 파악 /nlu"], True),
        (1070, [("postgresql", 0)], "PostgreSQL", ["메뉴·주문·대화 기록"], False),
    ]
    for x, logos, title, lines, hi in nodes:
        inner = "".join(logo(n, x + dx, y, 30 if len(logos) > 1 else 40) for n, dx in logos)
        s.append(tile(x, y, T, inner, hi))
        s.append(label(x, y + T/2 + 24, title, lines))
    s.append(wire(110 + T/2 + 6, y - 14, 330 - T/2 - 8, y - 14, "음성(WAV)", color=BLUE, mid=(220, y - 24)))
    s.append(wire(330 - T/2 - 6, y + 14, 110 + T/2 + 8, y + 14, "안내 목소리·화면", mid=(220, y + 32)))
    s.append(wire(330 + T/2 + 6, y, 590 - T/2 - 8, y, "/api/…/voice", color=BLUE))
    s.append(wire(590 + T/2 + 6, y - 14, 850 - T/2 - 8, y - 14, "/stt · /nlu", color=BLUE))
    s.append(wire(850 - T/2 - 6, y + 14, 590 + T/2 + 8, y + 14, "글자 · 표준 문장", mid=(720, y + 32)))
    s.append(f'<path d="M612,{y - T/2 - 2} C612,214 640,214 700,214 L1030,214 C1070,214 1070,214 1070,{y - T/2 - 8}" fill="none" stroke="{BLUE}" stroke-width="2.2" marker-end="url(#a{BLUE[1:]})"/>')
    s.append(f'<text x="960" y="207" text-anchor="middle" font-size="12" fill="{SUB}">SQL (SQLAlchemy)</text>')
    # 위쪽: 학습·외부 서비스
    top = [(850, "huggingface", "학습한 모델 3개", ["Release 로 배포"]), (590, "googlecloud", "Google Cloud TTS", ["사람 목소리 안내"]),
           (1010, "anthropic", "Claude (선택)", ["API 키가 있을 때만"])]
    for x, ic, t, ln in top:
        s.append(tile(x, 70, 52, logo(ic, x, 70, 28)))
        s.append(f'<text x="{x + 34}" y="66" font-size="13.5" font-weight="700" fill="{INK}">{t}</text>'
                 f'<text x="{x + 34}" y="84" font-size="12" fill="{SUB}">{ln[0]}</text>')
    s.append(wire(850, 98, 850, y - T/2 - 6, dash="5 4"))
    s.append(wire(590, 98, 590, y - T/2 - 6, dash="5 4"))
    s.append(wire(1010, 98, 872, y - T/2 - 4, dash="5 4"))
    # 아래: 개발·배포 흐름
    yb = 488
    dev = [(330, "githubactions", "GitHub Actions", "PR마다 4개 컨테이너 실행 확인"), (590, "docker", "이미지 3개", "Artifact Registry 에 커밋 태그로"),
           (850, "kubernetes", "scripts/deploy.sh", "배포 · rollback.sh 로 되돌리기"), (1070, "notion", "노션 작업 로그", "PR 내용을 자동 기록")]
    for x, ic, t, ln in dev:
        s.append(tile(x - 70, yb, 44, logo(ic, x - 70, yb, 24)))
        s.append(f'<text x="{x - 40}" y="{yb - 3}" font-size="13.5" font-weight="700" fill="{INK}">{t}</text>'
                 f'<text x="{x - 40}" y="{yb + 15}" font-size="12" fill="{SUB}">{ln}</text>')
    s.append(f'<text x="40" y="{yb + 4}" font-size="13.5" font-weight="700" fill="{SUB}">개발·배포</text>')
    s.append("</svg>")
    render(frame("손님의 말은 화면 → 백엔드 → 모델 서버를 거쳐 글자와 표준 문장이 되고, 백엔드가 주문 단계를 진행한다",
                 "파란 테두리 = 이 저장소의 세 서비스. 점선 = 시작할 때 받아 오거나 필요할 때만 쓰는 외부 자원. 출처: k8s/*.yaml, docker-compose.yml, model/README.md",
                 "\n".join(s), W + 88), OUT / "fig_architecture.png", W + 88, H + 150)


# ------------------------------------------------------------------ 2. 말 이해 순서
def fig_understanding():
    W, H = 1180, 340
    defs = marker(LINE) + marker(BLUE)
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs>{defs}</defs>']
    steps = [
        (105, "🎤", "음성 인식", ["whisper-small-elderly-v1", "어르신 목소리로 추가 학습", "화면별 힌트 단어"], "#FFFFFF"),
        (345, "📏", "① 규칙", ["backend nlu.py", "메뉴 이름·별명 사전", "결과가 항상 같고 빠름"], "#E8EDFD"),
        (585, "🏷️", "② 분류 모델", ["nlu-intent-v1 (RoBERTa)", "표준 문장 18개 중 하나", "CPU 약 8ms"], "#FFFFFF"),
        (825, "✍️", "③ 생성 모델", ["nlu-gen-v1 (Qwen 1.5B LoRA)", "메뉴 이름이 든 말까지", "서버 CPU 0.5~0.7초"], "#FFFFFF"),
        (1065, "🤖", "④ Claude", ["API 키가 있을 때만", "마지막 대안"], "#FFFFFF"),
    ]
    y = 112
    for x, em, t, lines, fill in steps:
        s.append(f'<rect x="{x-95}" y="{y-58}" width="190" height="132" rx="16" fill="{fill}" stroke="{BLUE if fill != "#FFFFFF" else "#D3DAE1"}" stroke-width="{2.2 if fill != "#FFFFFF" else 1.4}"/>')
        s.append(emoji(em, x, y - 28, 26))
        s.append(f'<text x="{x}" y="{y + 6}" text-anchor="middle" font-size="16" font-weight="700" fill="{INK}">{t}</text>')
        for k, ln in enumerate(lines):
            s.append(f'<text x="{x}" y="{y + 26 + k*16}" text-anchor="middle" font-size="12" fill="{SUB}">{ln}</text>')
    s.append(wire(202, y, 248, y, color=BLUE))
    s.append(wire(442, y, 488, y))
    s.append(wire(682, y, 728, y))
    s.append(wire(922, y, 968, y))
    for x, txt in ((225, "글자"), (465, "못 알아들으면"), (705, "자신 없으면"), (945, "그래도 모르면")):
        s.append(f'<text x="{x}" y="{y - 70}" text-anchor="middle" font-size="12" fill="{SUB}">{txt}</text>')
    # 아래: 다시 규칙으로
    s.append(f'<path d="M585,{y+74} C585,250 345,250 345,{y+80}" fill="none" stroke="{BLUE}" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#a{BLUE[1:]})"/>')
    s.append(f'<path d="M825,{y+74} C825,268 345,268 345,{y+80}" fill="none" stroke="{BLUE}" stroke-width="2" stroke-dasharray="5 4"/>')
    s.append(f'<path d="M1065,{y+74} C1065,286 345,286 345,{y+80}" fill="none" stroke="{BLUE}" stroke-width="2" stroke-dasharray="5 4"/>')
    s.append(f'<text x="735" y="326" text-anchor="middle" font-size="12.5" fill="{BLUE}">모델이 고친 "표준 문장"은 다시 ① 규칙과 메뉴 DB로 확인 → 없는 메뉴는 담기지 않는다</text>')
    s.append("</svg>")
    render(frame("손님 말은 규칙이 먼저 읽고, 못 알아들은 말만 모델이 표준 문장으로 고쳐 다시 규칙에 넘긴다",
                 '예: "봉투에 담아 줘" → 포장 · "그 매운 닭 버거 두 개" → 메뉴 이름 2개 주세요. 출처: backend/app/services/nlu.py (C안, PM 결정 2026-10-19), model/app/main.py /nlu',
                 "\n".join(s), W + 88), OUT / "fig_understanding.png", W + 88, H + 140)


# ------------------------------------------------------------------ 3. 모델 결과
def bar(x, y, w, frac, color, text, sub=""):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="5" fill="#EEF1F5"/>'
            f'<rect x="{x}" y="{y}" width="{w*frac:.1f}" height="22" rx="5" fill="{color}"/>'
            f'<text x="{x + w*frac + 8:.1f}" y="{y + 16}" font-size="14" font-weight="700" fill="{INK}">{text}</text>'
            + (f'<text x="{x + w*frac + 8:.1f}" y="{y + 34}" font-size="11.5" fill="{SUB}">{sub}</text>' if sub else ""))


def fig_results():
    W, H = 1180, 300
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    cols = [(30, "음성 인식 오류율 (CER, 낮을수록 좋음)", [("원본 Whisper small", 9.44 / 12, "#B8C2CC", "9.44%"), ("어르신 목소리 학습 후", 3.75 / 12, BLUE, "3.75%")],
             "AI Hub 노인 음성 100시간, 검증 1,000문장씩"),
            (420, "처음 보는 말 정답률 (높을수록 좋음)", [("분류 모델 nlu-intent-v1", 0.943, BLUE, "94.3%"), ("생성 모델 학습 전", 0.068, "#B8C2CC", "6.8%"), ("생성 모델 nlu-gen-v1", 0.953, BLUE, "95.3%")],
             "시험 문장 123개 · 148개 (학습에 안 쓴 말)"),
            (810, "화면별 힌트 단어 효과 (같은 녹음 63개)", [("힌트 전", 0.79, "#B8C2CC", "79%"), ("화면별 힌트 후 (#42)", 0.97, BLUE, "97%")],
             "음성 인식이 맞게 받아 적은 비율")]
    for x, title, rows, note in cols:
        s.append(f'<text x="{x}" y="34" font-size="15.5" font-weight="700" fill="{INK}">{title}</text>')
        for k, (name, frac, color, txt) in enumerate(rows):
            yy = 62 + k * 62
            s.append(f'<text x="{x}" y="{yy}" font-size="13" fill="{SUB}">{name}</text>')
            s.append(bar(x, yy + 8, 260, frac, color, txt))
        s.append(f'<text x="{x}" y="270" font-size="12" fill="{SUB}">{note}</text>')
    s.append("</svg>")
    render(frame("어르신 목소리로 다시 학습한 음성 인식은 오류가 절반 이하로, 처음 보는 말도 94~95% 알아들었다",
                 "출처: GitHub Release model-whisper-small-elderly-v1 · model-nlu-intent-v1 · model-nlu-gen-v1 · v1.0.0 노트 (팀 모델 담당 실험 기록)",
                 "\n".join(s), W + 88), OUT / "fig_results.png", W + 88, H + 130)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_architecture(); fig_understanding(); fig_results()
    print("ok")
