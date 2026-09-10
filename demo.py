"""디자인 확인용. 실제 시세를 쓰되 카드 문장은 미리 적어둔 것을 쓴다.

Claude 를 부르지 않으므로 API 비용이 들지 않는다.
카드 배치나 색을 만질 때는 이걸로 돌려보면 된다.

    python demo.py

카드마다 photo 항목이 있는데, 이게 그날 주제에 맞는 배경 사진을 찾는 검색어다.
실제 운영에서는 Claude 가 카드 내용에 맞춰 이 검색어까지 같이 만든다.
영어로 쓰는 편이 사진이 잘 나온다.
"""

import webbrowser

import assemble
import capture
import collect_market
import config
import render

# 2026년 9월 10일 실제 뉴스에서 뽑은 문장. 형식을 보여주기 위한 견본이다.
DEMO_TEXTS = {
    "cover": {
        "headline": "중동 긴장에 [[유가 100달러]] 돌파,\n밤새 뉴욕증시 하락",
        "photo": "oil pump jack sunset",
    },
    "overnight_headline": "위험자산은 팔고\n에너지와 달러로 피신",
    "overnight_photo": "new york stock exchange building",
    "macro": [
        {
            "label": "거시 이슈 · 지정학",
            "headline": "국제유가 4개월 만에\n[[배럴당 100달러]] 돌파",
            "photo": "oil tanker ship sea",
            "what": "중동 긴장이 높아지면서 브렌트유가 101달러, WTI가 100달러를 넘어섰다.",
            "chain": "유가 ↑ → 물가 ↑ → 금리 인하 지연 → 성장주·반도체에 부담",
            "impact": "증권가는 단기 투자심리에는 부담이지만 메모리 수요 자체와는 무관하다고 본다.",
            "link": "https://example.com/article-1",
        },
        {
            "label": "거시 이슈 · 통화정책",
            "headline": "월가 [[70%]]가 9월 동결 예상,\n시장은 인상에 무게",
            "photo": "federal reserve washington",
            "what": "로이터 설문에서 응답자 70%가 연준의 9월 금리 동결을 예상했다. 다만 유가 급등으로 인상론도 확산되고 있다.",
            "chain": "유가 ↑ → 물가 전망 ↑ → 동결 대신 인상 가능성",
            "impact": "금리가 오르면 성장주 밸류에이션에 직접 부담이 된다.",
            "link": "https://example.com/article-2",
        },
    ],
    "schedule": {
        "headline": "오늘 밤 미국 물가지표,\n금리 방향의 시험대",
        "photo": "calendar clock desk",
        "items": [
            {"time": "09:00", "text": "국내 증시 개장. 밤새 하락분 반영 여부"},
            {"time": "21:30", "text": "미국 소비자물가 발표"},
            {"time": "이번주", "text": "금요일 선물옵션 동시만기"},
        ],
        "note": "물가가 예상보다 높으면 금리 인하 기대가 후퇴한다",
    },
    "stocks": {
        "000660": {
            "cover_headline": "[[미국 ADR 7% 급등]]에도\n국내 주가는 보합 마감",
            "cover_photo": "memory chip semiconductor",
            "news": [
                {
                    "headline": "SK하이닉스 미국 ADR\n[[7% 폭등]]하며 최고가 경신",
                    "photo": "wall street stock trading",
                    "why": "국내 주식을 미국에서 사고팔 수 있게 만든 증서가 ADR이다. 이게 급등했다는 건 해외 투자자들이 회사를 더 좋게 보기 시작했다는 신호다.",
                    "link": "https://example.com/article-3",
                },
                {
                    "headline": "월가 \"마이크론도 좋지만\n[[AI 메모리 승자는 하이닉스]]\"",
                    "photo": "data center server room",
                    "why": "경쟁사인 마이크론 실적이 좋았는데도 월가가 하이닉스를 더 높게 평가했다. 고대역폭 메모리 시장에서 앞서 있다고 본 것이다.",
                    "link": "https://example.com/article-4",
                },
            ],
            "trend_headline": "닷새 동안 [[12%]] 오른 뒤\n숨 고르는 중",
            "trend_photo": "seoul city night skyline",
            "trend_note": "지난주 급등 이후 이틀째 보합권에 머물고 있다.",
        },
        "005930": {
            "cover_headline": "특별한 재료 없이\n[[보합]] 마감",
            "cover_photo": "smartphone electronics factory",
            "news": [
                {
                    "headline": "주가에 영향을 줄 만한\n뉴스가 없는 하루",
                    "photo": "empty office desk quiet",
                    "why": "오늘 나온 기사는 노조 내부 갈등과 사내 제도 관련 내용이 대부분이었다. 실적이나 사업에 직접 연결되는 소식은 없었다.",
                    "link": "",
                },
            ],
            "trend_headline": "3주째 [[27만원 선]]에서\n횡보",
            "trend_photo": "seoul skyline daytime",
            "trend_note": "방향을 정하지 못하고 좁은 폭에서 오르내리고 있다.",
        },
    },
    "closing": {
        "headline": "오늘 체크 3가지",
        "photo": "sunrise morning city skyline",
        "items": [
            "개장 직후 유가 충격이 반도체주에 얼마나 반영되는지",
            "하이닉스가 미국 ADR 급등을 따라가는지",
            "밤 9시 30분 미국 물가지표, 내일 아침 카드에서 정리",
        ],
    },
}


def main():
    codes = list(config.STOCKS.keys())

    print("실제 시세를 받아오는 중...")
    overnight = collect_market.overnight()
    stocks = {code: collect_market.korean_stock(code) for code in codes}

    report = assemble.build_report(DEMO_TEXTS, overnight, stocks, codes)

    print("카드별 배경 사진을 준비하는 중...")
    path = render.write_page(report, "demo.html")
    capture_page = render.write_capture_page(report, "demo_capture.html")

    total = sum(len(s["cards"]) for s in report["sections"])
    print(f"카드 {total}장 생성 완료")
    print(f"  웹페이지  {path}")

    png = capture.capture(capture_page, "demo_card.png")
    print(f"  대표 이미지 {png}  ({png.stat().st_size / 1024:.0f} KB)")

    shot = capture.capture_full(path, "demo_preview.png")
    print(f"  전체 미리보기 {shot}")

    webbrowser.open(path.as_uri())


if __name__ == "__main__":
    main()
