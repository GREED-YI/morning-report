"""시세 숫자와 카드 문장을 합쳐 최종 카드 목록을 만든다.

역할 분담이 여기서 드러난다.
  - 숫자(종가, 등락률, 지표 값)는 collect_market 이 가져온 값을 그대로 쓴다
  - 문장(헤드라인, 해설)은 Claude 가 쓴 것을 그대로 쓴다
  - 둘을 섞는 일만 이 파일이 한다

Claude 가 숫자를 만질 방법이 아예 없으므로, 없는 수치를 지어낼 수가 없다.
"""

from datetime import datetime, timedelta, timezone

import config

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def _won(value):
    """원 단위 큰 수를 조/억으로 읽기 쉽게."""
    if value >= 1e12:
        return f"약 {value / 1e12:.1f}조"
    return f"약 {value / 1e8:,.0f}억"


def _cover_stats(overnight):
    """커버 카드에 올릴 대표 지표 세 개를 고른다."""
    wanted = ["WTI 유가", "나스닥", "원/달러"]
    picked = [row for label in wanted for row in overnight if row["label"] == label]
    return [
        {"label": row["label"], "value": row["value"].split(" ")[0], "direction": row["direction"]}
        for row in picked[:3]
    ]


def build_report(texts, overnight, stocks, stock_codes):
    """카드 전체를 조립한다.

    texts       : Claude 가 만든 문장 묶음
    overnight   : collect_market.overnight() 결과
    stocks      : {종목코드: collect_market.korean_stock() 결과}
    stock_codes : 이 사람이 구독한 종목 순서
    """
    now = datetime.now(KST)
    sections = []

    # ── 시장 전체 ────────────────────────────────────────────
    market_cards = [
        {
            "type": "cover",
            "label": f"{now.month}월 {now.day}일 ({WEEKDAYS[now.weekday()]}) · 개장 전 브리핑",
            "headline": texts["cover"]["headline"],
            "photo_topic": texts["cover"].get("photo", ""),
            "stats": _cover_stats(overnight),
            "foot": "숫자는 해외 시장 마감 기준",
            "foot_right": "제작 SH.YI",
        },
        {
            "type": "overnight",
            "label": "밤새 지표",
            "headline": texts["overnight_headline"],
            "photo_topic": texts.get("overnight_photo", ""),
            "rows": [
                {"label": r["label"], "value": r["value"], "direction": r["direction"]}
                for r in overnight
            ],
            "foot": "빨강은 올랐다, 파랑은 내렸다",
        },
    ]

    for issue in texts["macro"][: config.MAX_MACRO_ISSUES]:
        market_cards.append({
            "type": "macro",
            "label": issue["label"],
            "headline": issue["headline"],
            "photo_topic": issue.get("photo", ""),
            "what": issue["what"],
            "chain": issue.get("chain", ""),
            "impact": issue.get("impact", ""),
            "link": issue.get("link", ""),
        })

    schedule = texts.get("schedule")
    if schedule and schedule.get("items"):
        market_cards.append({
            "type": "schedule",
            "label": "오늘 일정",
            "headline": schedule["headline"],
            "photo_topic": schedule.get("photo", ""),
            "items": schedule["items"],
            "foot": schedule.get("note", ""),
        })

    sections.append({"title": "시장 전체", "cards": market_cards})

    # ── 종목별 ───────────────────────────────────────────────
    for code in stock_codes:
        data = stocks[code]
        text = texts["stocks"][code]
        cards = [{
            "type": "stock_cover",
            "label": data["name"],
            "headline": text["cover_headline"],
            "photo_topic": text.get("cover_photo", ""),
            "stats": [
                {"label": "전일 종가", "value": f"{data['close']:,}"},
                {"label": "등락", "value": f"{data['change_pct']:+.2f}%", "direction": data["direction"]},
                {"label": "거래대금", "value": _won(data["approx_value_krw"])},
            ],
            "foot": "숫자는 전 거래일 확정 시세",
            "foot_right": data["date"],
        }]

        for n, news in enumerate(text["news"][: config.MAX_STOCK_NEWS]):
            cards.append({
                "type": "stock_news" if n == 0 else "stock_news2",
                "label": f"{data['name']} 뉴스 {n + 1}",
                "headline": news["headline"],
                "photo_topic": news.get("photo", ""),
                "why": news["why"],
                "link": news.get("link", ""),
            })

        closes = [t["close"] for t in data["trend"]]
        floor = min(closes)
        span = (max(closes) - floor) or 1
        cards.append({
            "type": "trend",
            "label": "최근 닷새",
            "headline": text["trend_headline"],
            "photo_topic": text.get("trend_photo", ""),
            "bars": True,
            "rows": [
                {
                    "label": t["date"],
                    "value": f"{t['close']:,}",
                    # 막대는 최저가를 바닥으로 잡아야 차이가 눈에 보인다
                    "weight": 20 + (t["close"] - floor) / span * 80,
                    "direction": "up" if t["close"] >= closes[0] else "down",
                }
                for t in data["trend"]
            ],
            "note": text.get("trend_note", ""),
            "foot": "단위: 원",
        })

        sections.append({"title": f"내 종목 · {data['name']}", "cards": cards})

    # ── 마무리 ───────────────────────────────────────────────
    sections.append({"title": "마무리", "cards": [{
        "type": "closing",
        "label": "오늘 이것만",
        "headline": texts["closing"]["headline"],
        "photo_topic": texts["closing"].get("photo", ""),
        "items": texts["closing"]["items"],
        "foot": "뉴스 요약이며 투자 권유가 아닙니다",
        "foot_right": "내일 07:00",
    }]})

    return {
        "date": now.strftime("%Y-%m-%d"),
        "weekday": WEEKDAYS[now.weekday()],
        "sections": sections,
    }
