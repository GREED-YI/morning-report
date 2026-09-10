"""뉴스 제목을 읽고 카드에 들어갈 문장을 만든다.

모델에게 시키는 일과 시키지 않는 일이 뚜렷하게 갈린다.

  시키는 것    : 기사 고르기, 헤드라인 쓰기, 왜 중요한지 풀어쓰기, 사진 검색어 정하기
  안 시키는 것 : 숫자 만들기, 기사 주소 쓰기, 오를지 내릴지 예측하기

기사 주소는 모델이 쓰지 않고 번호로만 고르게 한다. 코드가 그 번호를 실제 주소로
바꾸므로, 없는 주소를 지어내는 일이 구조적으로 불가능하다.
"""

import collect_news
import config
import photos
import providers

_SYSTEM_TEMPLATE = """너는 가족에게 보내는 아침 주식 브리핑 카드뉴스의 편집자다.
읽는 사람은 주식을 조금 아는 40~60대 가족이다. 전문 투자자가 아니다.

# 반드시 지킬 것

1. 예측하지 마라.
   "오를 것이다", "지금이 기회다", "사야 한다" 같은 말은 절대 쓰지 않는다.
   시장의 해석을 전할 때는 "증권가는 ~로 본다", "~라는 분석이 나온다" 처럼
   출처가 있는 시각으로만 쓴다.

2. 숫자를 만들지 마라. 그리고 주어진 숫자와 어긋나지 마라.
   종가, 등락률, 지표 값은 시스템이 따로 채운다. 네가 쓸 필요가 없다.
   기사 제목에 있는 숫자는 그 제목에 분명히 적혀 있을 때만 인용한다.

   중요한 함정이 하나 있다. 기사 제목의 숫자는 몇 시간 전 값이고,
   카드에 함께 표시될 지표 값은 방금 받은 값이라 서로 다를 수 있다.
   같은 카드 안에서 두 숫자가 어긋나면 읽는 사람이 헷갈린다.
   예를 들어 지표에 WTI 유가 99.35 라고 적혀 있으면 헤드라인에
   "100달러 돌파" 라고 쓰면 안 된다. "100달러 코앞" 처럼 지금 값에 맞춰 쓴다.
   헤드라인을 쓰기 전에 아래에 주어진 지표 값을 먼저 확인해라.

3. 주가와 상관없는 기사는 버려라.
   노조 갈등, 사내 제도, 지역 행사, 사회공헌, 채용, 수상, 전시회 참가 같은
   기사는 아무리 많이 나와도 고르지 않는다. 실적, 계약, 신제품, 수요,
   규제, 경쟁사 동향처럼 회사의 돈벌이에 연결되는 것만 고른다.

4. 억지로 채우지 마라.
   고를 만한 기사가 없으면 그렇다고 솔직히 쓴다.
   "오늘은 주가에 영향을 줄 만한 뉴스가 없었다" 도 훌륭한 카드다.

5. 쉬운 말로 써라.
   HBM, ADR, 컨센서스 같은 말을 쓸 거면 같은 문장 안에서 한 번 풀어준다.
   예: "국내 주식을 미국에서 사고팔 수 있게 만든 증서인 ADR"

# 글쓰기 형식

- 헤드라인은 2줄. 줄을 나눌 자리에 <br> 을 넣는다. 한 줄은 공백 포함 20자 안쪽.
  예: "치솟는 유가와 금리<br>흔들리는 글로벌 증시"
- 헤드라인에서 가장 중요한 말 하나를 [[이렇게]] 감싼다. 카드마다 딱 한 곳만.
  회사 이름이나 뻔한 말 말고, 그날 새로 생긴 사실을 감싼다.
- 종목 카드 헤드라인에 회사 이름을 쓰지 마라. 카드에 이미 이름표가 붙어 있어서
  같은 말이 두 번 나온다. 회사 이름 자리에 그날 무슨 일이 있었는지를 넣는다.
- 해설은 두세 문장. 문장을 짧게 끊는다.
- 이모지를 쓰지 않는다.

# 사진 주제 (photo)

카드 배경에 깔릴 사진의 주제다. 아래 목록에서 하나를 고른다. 목록에 없는 말은
쓸 수 없다. 사진은 미리 골라 둔 것들이라, 주제만 맞으면 그림은 알아서 좋은 게 나온다.

{topics}

카드 내용과 가장 가까운 것을 고른다.
유가나 에너지 이야기면 oil, 금리나 중앙은행이면 centralbank,
전쟁·해운·수출길이면 geopolitics, 칩이나 메모리면 semiconductor,
AI 서버 수요면 datacenter, 증시 흐름이면 trading, 해외 증시면 exchange,
환율이면 currency, 국내 시장이면 seoul, 생산·공장이면 factory,
전자제품이면 electronics, 일정이면 schedule, 마무리 카드면 sunrise 나 checklist.

같은 브리핑 안에서 되도록 서로 다른 주제를 고른다. 카드마다 다른 그림이 나가야 한다.

# 기사 고르기

기사마다 앞에 번호가 붙어 있다. 고른 기사의 번호를 source_index 에 적는다.
기사 주소는 네가 쓰지 않는다. 고를 기사가 없으면 source_index 를 -1 로 둔다.
"""

SYSTEM = _SYSTEM_TEMPLATE.format(
    topics="\n".join(f"  {name}" for name in photos.topics())
)

# 두 모델이 공통으로 이해하는 형식만 쓴다. (type, properties, required, items, enum)
_TEXT = {"type": "string"}

# 사진 주제는 창고에 있는 것만 고르게 한다. 목록 밖의 값이 나올 수 없다.
_TOPIC = {
    "type": "string",
    "enum": photos.topics(),
    "description": "카드 배경 사진의 주제. 목록에 있는 것만 쓸 것",
}

MARKET_SCHEMA = {
    "type": "object",
    "properties": {
        "cover_headline": {"type": "string", "description": "오늘 시장 전체를 한 줄로. 2~3줄"},
        "cover_photo": _TOPIC,
        "overnight_headline": {"type": "string", "description": "밤새 해외 시장의 성격을 한 줄로"},
        "overnight_photo": _TOPIC,
        "macro": {
            "type": "array",
            "description": "시장 전체를 흔든 이슈. 1~2개",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "예: 거시 이슈 · 지정학"},
                    "headline": _TEXT,
                    "photo": _TOPIC,
                    "what": {"type": "string", "description": "무슨 일이 있었는지 한두 문장"},
                    "chain": {
                        "type": "string",
                        "description": "영향이 퍼지는 경로. 예: 유가 ↑ → 물가 ↑ → 금리 인하 지연 → 반도체 부담",
                    },
                    "impact": {"type": "string", "description": "우리 종목에 어떤 뜻인지. 출처 있는 시각으로"},
                    "source_index": {"type": "integer"},
                },
                "required": ["label", "headline", "photo", "what", "chain", "impact", "source_index"],
            },
        },
        "schedule": {
            "type": "object",
            "properties": {
                "headline": _TEXT,
                "photo": _TOPIC,
                "items": {
                    "type": "array",
                    "description": "오늘 챙길 일정 2~3개",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time": {"type": "string", "description": "예: 09:00, 21:30, 이번주"},
                            "text": _TEXT,
                        },
                        "required": ["time", "text"],
                    },
                },
                "note": _TEXT,
            },
            "required": ["headline", "photo", "items", "note"],
        },
        "closing": {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "고정: 오늘 체크 3가지"},
                "photo": _TOPIC,
                "items": {"type": "array", "description": "3개", "items": _TEXT},
            },
            "required": ["headline", "photo", "items"],
        },
    },
    "required": ["cover_headline", "cover_photo", "overnight_headline",
                 "overnight_photo", "macro", "schedule", "closing"],
}

STOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "cover_headline": {"type": "string", "description": "이 종목의 오늘을 한 줄로"},
        "cover_photo": _TOPIC,
        "news": {
            "type": "array",
            "description": "주가와 관련된 기사 1~2개. 없으면 없다고 쓴 카드 한 장",
            "items": {
                "type": "object",
                "properties": {
                    "headline": _TEXT,
                    "photo": _TOPIC,
                    "why": {"type": "string", "description": "왜 중요한지 쉬운 말로 두세 문장"},
                    "source_index": {"type": "integer"},
                },
                "required": ["headline", "photo", "why", "source_index"],
            },
        },
        "trend_headline": {"type": "string", "description": "최근 닷새 주가 흐름을 한 줄로"},
        "trend_photo": _TOPIC,
        "trend_note": _TEXT,
    },
    "required": ["cover_headline", "cover_photo", "news",
                 "trend_headline", "trend_photo", "trend_note"],
}


def _numbered(articles):
    """모델에게 보여줄 기사 목록. 주소는 빼고 번호와 제목만 준다."""
    return "\n".join(
        f"{i}. [{a['published']}] {a['title']}" for i, a in enumerate(articles)
    )


def _indicators(overnight):
    return "\n".join(f"- {row['label']}: {row['value']}" for row in overnight)


def _attach_links(items, articles):
    """모델이 고른 번호를 실제 기사 주소로 바꾼다."""
    for item in items:
        index = item.pop("source_index", -1)
        item["link"] = articles[index]["link"] if 0 <= index < len(articles) else ""
    return items


# ── 시장 전체 ───────────────────────────────────────────────────

def market(overnight, articles):
    prompt = f"""오늘 아침 브리핑의 '시장 전체' 부분을 만들어라.

## 밤새 해외 시장
{_indicators(overnight)}

## 최근 24시간 거시 뉴스 제목
{_numbered(articles)}

## 할 일
1. cover_headline: 위 지표와 뉴스를 통틀어 오늘 시장을 한마디로.
2. overnight_headline: 밤새 해외 시장이 어떤 성격이었는지.
3. macro: 시장 전체를 흔든 이슈 1~2개. 각각 chain 에 영향 경로를 화살표로 적고,
   impact 에는 반도체 종목(SK하이닉스, 삼성전자)에 어떤 뜻인지 적어라.
4. schedule: 오늘 챙길 일정. 국내 개장 시각은 09:00 이다.
   뉴스에서 발표 예정인 지표나 행사가 보이면 넣어라.
5. closing: 오늘 체크할 것 3가지. 지표가 아니라 '무엇을 지켜볼지' 로 쓴다.
"""
    result = providers.generate_json(SYSTEM, prompt, MARKET_SCHEMA)
    _attach_links(result.get("macro", []), articles)
    return result


# ── 종목별 ──────────────────────────────────────────────────────

def stock(code, data, articles, market_headline):
    info = config.STOCKS[code]
    trend = " → ".join(f"{t['date']} {t['close']:,}원" for t in data["trend"])
    peers = ", ".join(f"{p['ticker']} {p['change_pct']:+.2f}%" for p in data.get("peer_rows", []))

    prompt = f"""'{info['name']}' 부분을 만들어라.

## 오늘 시장 분위기
{market_headline}

## 이 종목의 시세 (이미 카드에 들어가므로 다시 쓰지 마라)
- 전일 종가 {data['close']:,}원 ({data['change_pct']:+.2f}%)
- 최근 닷새: {trend}
{f"- 관련 미국 종목 야간: {peers}" if peers else ""}

## 최근 24시간 이 종목 관련 뉴스 제목
{_numbered(articles)}

## 할 일
1. cover_headline: 이 종목의 오늘을 한마디로. 시장 분위기와 엮어도 좋다.
2. news: 주가에 영향을 줄 만한 기사 1~2개를 골라 헤드라인과 해설을 써라.
   고를 것이 없으면 news 를 한 개만 만들고, 그 안에 오늘은 주가와 관련된
   뉴스가 없었다는 사실을 쓰고 source_index 를 -1 로 둔다.
3. trend_headline, trend_note: 닷새 흐름을 보고 어떤 모양인지 담담하게.
   앞으로 어떻게 될지는 쓰지 마라.
"""
    result = providers.generate_json(SYSTEM, prompt, STOCK_SCHEMA)
    _attach_links(result.get("news", []), articles)
    return result


# ── 한꺼번에 ────────────────────────────────────────────────────

def build_texts(codes, overnight, stocks):
    """카드에 들어갈 문장을 모두 만들어 assemble 이 쓰는 모양으로 돌려준다."""
    print(f"카드 문장 생성 중 ({providers.describe()})")

    print("  거시 뉴스 수집...")
    macro_articles = collect_news.macro_news()
    print(f"  시장 전체 카드 작성... (기사 {len(macro_articles)}건)")
    market_texts = market(overnight, macro_articles)

    texts = {
        "cover": {
            "headline": market_texts["cover_headline"],
            "photo": market_texts["cover_photo"],
        },
        "overnight_headline": market_texts["overnight_headline"],
        "overnight_photo": market_texts["overnight_photo"],
        "macro": market_texts["macro"],
        "schedule": market_texts["schedule"],
        "closing": market_texts["closing"],
        "stocks": {},
    }

    for code in codes:
        name = config.STOCKS[code]["name"]
        articles = collect_news.stock_news(code)
        print(f"  {name} 카드 작성... (기사 {len(articles)}건)")
        texts["stocks"][code] = stock(
            code, stocks[code], articles, market_texts["cover_headline"]
        )

    return texts
