"""카드뉴스 HTML 생성.

카드 데이터(딕셔너리)를 받아 폰에서 옆으로 넘겨 보는 웹 페이지를 만든다.
디자인 원칙은 세 가지다.

  1. 사진 배경 + 남색 단색 오버레이 + 흰 굵은 고딕
  2. 글은 항상 카드 아래쪽에만. 사진과 겹치지 않게 아래쪽 오버레이를 짙게 깐다
  3. 색은 의미가 있을 때만. 상승 빨강, 하락 파랑, 헤드라인 핵심어 하늘색

헤드라인 안에서 강조하고 싶은 말은 [[이렇게]] 감싸면 하늘색이 된다.
"""

import html
import re
import shutil
from pathlib import Path

import photos

OUT_DIR = Path(__file__).parent / "out"

# 카드 종류마다 배경 사진이 정해져 있다. assets/SOURCES.md 에 출처가 있다.
PHOTOS = {
    "cover": "cover.jpg",
    "overnight": "overnight.jpg",
    "macro": "macro1.jpg",
    "schedule": "macro2.jpg",
    "stock_cover": "stock.jpg",
    "stock_news": "news1.jpg",
    "stock_news2": "news2.jpg",
    "trend": "trend.jpg",
    "closing": "closing.jpg",
}


def _text(value):
    """문장을 HTML 로 바꾼다.

    태그는 전부 막되 두 가지 표기만 허용한다.
      [[강조]]  ->  하늘색 글씨
      줄바꿈    ->  <br>   (\\n 으로 쓰거나 <br> 로 써도 된다)
    이렇게 하면 Claude 가 만든 문장이 페이지 구조를 망가뜨릴 수 없다.
    """
    escaped = html.escape(str(value or ""))
    # 줄바꿈으로 인정하는 세 가지 표기를 모두 진짜 줄바꿈으로 모은다.
    # 모델이 JSON 을 쓸 때 역슬래시를 한 번 더 감싸는 일이 있어서,
    # 화면에 \n 두 글자가 그대로 찍히는 사고가 실제로 났다.
    escaped = escaped.replace("&lt;br&gt;", "\n").replace("&lt;br/&gt;", "\n")
    escaped = escaped.replace("\\n", "\n")
    escaped = re.sub(r"\[\[(.+?)\]\]", r'<span class="hl">\1</span>', escaped)
    return escaped.replace("\n", "<br>")


def _dir_class(direction):
    return {"up": " up", "down": " down"}.get(direction, "")


# ── 카드 종류별 본문 ────────────────────────────────────────────

def _stats(items):
    """종가·등락 같은 숫자 세 개를 나란히."""
    cells = "".join(
        f'<div><div class="k">{html.escape(i["label"])}</div>'
        f'<div class="v num{_dir_class(i.get("direction"))}">{html.escape(i["value"])}</div></div>'
        for i in items
    )
    return f'<div class="stat">{cells}</div>'


def _rows(items, bars=False):
    """지표 목록. bars 를 켜면 값 크기만큼 막대를 그린다."""
    if bars and items:
        biggest = max(abs(i.get("weight", 0)) for i in items) or 1
    out = []
    for i in items:
        cls = _dir_class(i.get("direction"))
        bar = ""
        if bars:
            width = abs(i.get("weight", 0)) / biggest * 100
            bar = f'<span class="bar"><i class="{cls.strip()}" style="width:{width:.0f}%"></i></span>'
        out.append(
            f'<div class="row"><span>{html.escape(i["label"])}</span>{bar}'
            f'<span class="v num{cls}">{html.escape(i["value"])}</span></div>'
        )
    return f'<div class="rows">{"".join(out)}</div>'


def _list(items, numbered=True):
    """오늘 체크 3가지, 오늘 일정처럼 줄 세운 목록."""
    out = []
    for n, item in enumerate(items, 1):
        marker = str(n) if numbered else html.escape(item.get("time", ""))
        cls = "" if numbered else " t"
        out.append(
            f'<li><i class="{cls.strip()}">{marker}</i>'
            f'<span>{_text(item["text"] if isinstance(item, dict) else item)}</span></li>'
        )
    return f'<ul class="check">{"".join(out)}</ul>'


def _body(card):
    """카드 종류에 따라 헤드라인 아래 들어갈 내용을 만든다."""
    kind = card["type"]
    parts = []

    if card.get("stats"):
        parts.append(_stats(card["stats"]))
    if card.get("rows"):
        parts.append(_rows(card["rows"], bars=card.get("bars", False)))

    if kind == "macro":
        inner = f'<b>무슨 일.</b> {_text(card["what"])}'
        if card.get("chain"):
            inner += f'<span class="chain">{_text(card["chain"])}</span>'
        if card.get("impact"):
            inner += f'<b>우리 종목엔.</b> {_text(card["impact"])}'
        parts.append(f'<div class="sub">{inner}</div>')
    elif kind in ("stock_news", "stock_news2"):
        parts.append(f'<div class="sub"><b>왜 중요한가.</b> {_text(card["why"])}</div>')
    elif card.get("note"):
        parts.append(f'<div class="sub">{_text(card["note"])}</div>')

    if card.get("items"):
        parts.append(_list(card["items"], numbered=(kind == "closing")))

    return "".join(parts)


def _foot(card):
    """카드 아래 한 줄. 기사 카드에는 원문 링크만 넣고 언론사 이름은 넣지 않는다."""
    left = card.get("foot", "")
    if card.get("link"):
        left = f'<a class="src" href="{html.escape(card["link"])}" target="_blank" rel="noopener">기사 원문 보기 ↗</a>'
    else:
        left = f"<span>{html.escape(left)}</span>"
    return f'<div class="foot">{left}<span>{html.escape(card.get("foot_right", ""))}</span></div>'


def _card(card, index, total):
    photo = card.get("photo_file") or PHOTOS.get(card["type"], "cover.jpg")
    big = " xl" if card["type"] in ("cover", "stock_cover") else ""
    return f"""
<section class="card" style="background-image:url(assets/{photo})">
  <div class="top">
    <span class="wordmark"><i></i>모닝 리포트</span>
    <span class="pg">{index}/{total}</span>
  </div>
  <div class="bottom">
    <span class="label">{html.escape(card["label"])}</span>
    <h2 class="{big.strip()}">{_text(card["headline"])}</h2>
    {_body(card)}
    {_foot(card)}
  </div>
</section>"""


# ── 페이지 ──────────────────────────────────────────────────────

CSS = """
:root{--navy:#0B1626;--accent:#2F7CF6;--up:#FF6B63;--down:#6FA8FF;--hl:#8CC3FF;
--bg:#F2F3F5;--ink:#101418;--ink2:#4A5460;--line:#DCE0E5;--surface:#fff}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#101418;--ink:#EDF0F3;--ink2:#B7BEC7;--line:#262C34;--surface:#171C22}}
:root[data-theme="dark"]{--bg:#101418;--ink:#EDF0F3;--ink2:#B7BEC7;--line:#262C34;--surface:#171C22}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:560px;margin:0 auto;padding:20px 0 40px}
header{display:flex;justify-content:space-between;align-items:baseline;padding:0 16px 14px;gap:12px}
header h1{font-size:17px;font-weight:900;margin:0;letter-spacing:-.02em}
header .d{font-size:13px;color:var(--ink2);font-weight:500}
.deck{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:0 16px 14px;
scrollbar-width:thin;-webkit-overflow-scrolling:touch}
.deck::-webkit-scrollbar{height:5px}
.deck::-webkit-scrollbar-thumb{background:var(--line);border-radius:3px}
.card{flex:0 0 min(88vw,420px);aspect-ratio:1;border-radius:10px;position:relative;overflow:hidden;
scroll-snap-align:center;color:#fff;background-size:cover;background-position:center;
display:flex;flex-direction:column;padding:20px 22px 18px;box-shadow:0 1px 3px rgba(0,0,0,.14)}
.card::before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,
rgba(11,22,38,.62) 0%,rgba(11,22,38,.18) 28%,rgba(11,22,38,.30) 48%,rgba(11,22,38,.90) 74%,rgba(11,22,38,.97) 100%)}
.card>*{position:relative}
.top{display:flex;justify-content:space-between;align-items:center}
.wordmark{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:900;letter-spacing:-.01em}
.wordmark i{width:18px;height:18px;border-radius:4px;background:#fff;display:grid;place-items:center}
.wordmark i::after{content:"";width:8px;height:8px;border-radius:50%;background:var(--navy);box-shadow:4px -4px 0 -2px var(--accent)}
.pg{font-family:ui-monospace,Consolas,monospace;font-size:12px;font-weight:600;opacity:.85}
.bottom{margin-top:auto}
.label{display:inline-block;background:var(--accent);color:#fff;font-size:12px;font-weight:700;
padding:3px 10px;border-radius:3px;margin-bottom:10px}
.card h2{font-size:23px;line-height:1.32;font-weight:900;letter-spacing:-.03em;margin:0;
word-break:keep-all;text-wrap:balance;text-shadow:0 1px 12px rgba(0,0,0,.35)}
.card h2.xl{font-size:26px}
.sub{font-size:13px;line-height:1.6;margin-top:8px;font-weight:500;color:rgba(255,255,255,.9);word-break:keep-all}
.sub b{font-weight:900;color:#fff;display:inline}
.sub .chain{display:block;margin:4px 0;font-weight:700;color:var(--hl)}
.foot{display:flex;justify-content:space-between;gap:10px;font-size:11px;font-weight:500;
color:rgba(255,255,255,.7);margin-top:12px;padding-top:8px;border-top:1px solid rgba(255,255,255,.18)}
.foot a.src{color:var(--hl);text-decoration:none;font-weight:700}
.num{font-family:ui-monospace,Consolas,monospace;font-weight:600;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}.hl{color:var(--hl)}
.stat{display:flex;gap:18px;margin-top:10px;flex-wrap:wrap}
.stat .k{font-size:11px;font-weight:700;color:rgba(255,255,255,.7)}
.stat .v{font-size:18px;font-weight:900;letter-spacing:-.02em;line-height:1.2}
.rows{margin-top:10px;display:grid;gap:5px}
.row{display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:500}
.row .bar{flex:1;height:4px;background:rgba(255,255,255,.22);margin:0 10px;border-radius:2px;overflow:hidden}
.row .bar i{display:block;height:100%;background:#fff}
.row .bar i.up{background:var(--up)}.row .bar i.down{background:var(--down)}
.row .v{font-weight:900}
.check{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:7px}
.check li{display:flex;gap:9px;font-size:13.5px;font-weight:500;line-height:1.5;word-break:keep-all}
.check li i{flex:0 0 20px;height:20px;border-radius:3px;background:var(--accent);font-size:11px;
font-weight:900;display:grid;place-items:center;font-style:normal;margin-top:2px}
.check li i.t{background:rgba(255,255,255,.18);flex-basis:46px;font-size:10.5px;
font-family:ui-monospace,Consolas,monospace}
.sect{display:flex;align-items:center;gap:10px;font-size:11px;font-weight:700;color:var(--ink2);
letter-spacing:.06em;margin:14px 16px 8px}
.sect::after{content:"";flex:1;height:1px;background:var(--line)}
footer{padding:18px 16px 0;font-size:12px;color:var(--ink2);line-height:1.7;border-top:1px solid var(--line);margin:8px 16px 0}
footer b{color:var(--ink)}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>모닝 리포트 {date}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap">
<style>{css}</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>모닝 리포트</h1>
    <span class="d">{date} ({weekday}) 07:00</span>
  </header>
{sections}
  <footer>
    숫자는 전 거래일 종가와 밤새 해외 시장 기준입니다.<br>
    이 페이지는 뉴스 요약이며 투자 권유가 아닙니다.<br>
    <b>제작 SH.YI</b>{credits}
  </footer>
</div>
</body>
</html>
"""


def render_page(report):
    """카드 데이터를 받아 완성된 HTML 문자열을 돌려준다."""
    total = sum(len(s["cards"]) for s in report["sections"])
    index = 0
    blocks = []

    for section in report["sections"]:
        cards = []
        for card in section["cards"]:
            index += 1
            cards.append(_card(card, index, total))
        blocks.append(
            f'  <div class="sect">{html.escape(section["title"])}</div>\n'
            f'  <div class="deck">{"".join(cards)}\n  </div>'
        )

    # 출처를 밝혀야 하는 사진이 있을 때만 페이지 맨 아래에 적는다
    lines = report.get("credits") or []
    credits = ""
    if lines:
        credits = "<br><span style='opacity:.75'>사진 " + " / ".join(
            html.escape(line) for line in lines
        ) + "</span>"

    return PAGE.format(
        date=report["date"],
        weekday=report["weekday"],
        css=CSS,
        sections="\n".join(blocks),
        credits=credits,
    )


def _sync_assets():
    """사진을 out/assets/ 로 복사한다.

    out/ 폴더 하나만 통째로 GitHub Pages 에 올리면 되도록,
    페이지가 참조하는 파일은 전부 out/ 안에 두는 구조로 만든다.
    """
    source = Path(__file__).parent / "assets"
    target = OUT_DIR / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for photo in source.glob("*.jpg"):
        shutil.copyfile(photo, target / photo.name)


def resolve_photos(report):
    """카드마다 주제에 맞는 배경 사진을 창고에서 꺼내 붙인다.

    카드에 photo_topic 이 있으면 그 주제의 사진을, 없으면 카드 종류별
    기본 사진을 쓴다. 주제마다 사진이 여러 장이라 날짜와 카드 번호를 섞어
    고르므로 날마다, 카드마다 다른 그림이 나간다.

    고른 사진은 out/assets/ 에 번호를 붙여 복사한다. out/ 폴더 하나만
    통째로 올리면 페이지가 그대로 뜨게 하려는 것이다.
    """
    OUT_DIR.mkdir(exist_ok=True)
    target = OUT_DIR / "assets"
    target.mkdir(parents=True, exist_ok=True)

    # 날짜를 숫자로 바꿔 그날의 시작점으로 삼는다
    day_seed = sum(int(part) for part in report["date"].split("-"))
    used = set()
    index = 0

    for section in report["sections"]:
        for card in section["cards"]:
            index += 1
            topic = card.get("photo_topic")
            if not topic or topic not in photos.index():
                card["photo_file"] = PHOTOS.get(card["type"], "cover.jpg")
                continue

            # 같은 브리핑 안에서 같은 사진이 두 번 나오지 않게 한 칸씩 밀어 본다
            pool = len(photos.index()[topic])
            for offset in range(pool):
                source, _ = photos.pick(topic, day_seed + index + offset)
                if source not in used or offset == pool - 1:
                    break
            used.add(source)

            name = f"card{index:02d}.jpg"
            shutil.copyfile(source, target / name)
            card["photo_file"] = name

    return []


def write_page(report, filename="index.html"):
    """HTML 을 out/ 폴더에 쓴다. 사진도 같이 준비하고 복사한다."""
    OUT_DIR.mkdir(exist_ok=True)
    _sync_assets()
    report["credits"] = resolve_photos(report)
    path = OUT_DIR / filename
    path.write_text(render_page(report), encoding="utf-8")
    return path


# ── 카톡 대표 이미지용 ──────────────────────────────────────────

CAPTURE_PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>capture</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap">
<style>{css}
html,body{{margin:0;padding:0;background:var(--navy)}}
.card{{flex:none;width:400px;height:400px;border-radius:0;box-shadow:none}}
</style>
</head>
<body>{card}</body>
</html>
"""


def write_capture_page(report, filename="capture.html"):
    """카톡에 보낼 대표 이미지를 찍기 위한 페이지.

    카드 한 장만 400x400 으로 그린다. 캡처할 때 배율을 2배로 주면
    카카오 권장 크기인 800x800 PNG 가 나온다. 웹에서 보는 카드와
    같은 CSS 를 쓰므로 디자인이 어긋날 일이 없다.
    """
    OUT_DIR.mkdir(exist_ok=True)
    _sync_assets()
    first = report["sections"][0]["cards"][0]
    total = sum(len(s["cards"]) for s in report["sections"])
    path = OUT_DIR / filename
    path.write_text(
        CAPTURE_PAGE.format(css=CSS, card=_card(first, 1, total)),
        encoding="utf-8",
    )
    return path
