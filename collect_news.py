"""뉴스 수집. 구글 뉴스 RSS 에서 제목과 원문 링크를 모은다.

네이버 검색 API 는 쓰지 않는다. 2026년 9월 7일 시행된 약관이
검색 결과를 AI 에 입력하는 행위 자체를 금지하는데, 기사를 Claude 로
요약하는 우리 구조가 정확히 거기 해당하기 때문이다.

구글 뉴스 RSS 는 제목·언론사·원문 링크만 준다. 본문은 가져오지 않는다.
Claude 에게는 제목 여러 개를 한꺼번에 주고 "무슨 일이 있었는지" 를 묶게 한다.
같은 사건을 여러 언론사가 다르게 쓴 제목 스무 개면 사건의 윤곽은 충분히 잡힌다.
"""

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import config

RSS = "https://news.google.com/rss/search"
UA = "Mozilla/5.0 (compatible; MorningReport/0.1)"
KST = timezone(timedelta(hours=9))


def _clean(text):
    """제목에 섞여 오는 HTML 태그와 군더더기를 걷어낸다."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def search(query, hours=24, limit=15):
    """검색어 하나로 최근 기사를 가져온다."""
    params = urllib.parse.urlencode({
        "q": query,
        "hl": "ko",
        "gl": "KR",
        "ceid": "KR:ko",
    })
    req = urllib.request.Request(f"{RSS}?{params}", headers={"User-Agent": UA})

    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            root = ET.fromstring(res.read())
    except Exception as e:
        print(f"  [경고] '{query}' 수집 실패: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        link = item.findtext("link") or ""
        source = _clean(item.findtext("source")) or "출처 미상"

        try:
            published = parsedate_to_datetime(item.findtext("pubDate"))
        except Exception:
            continue
        if published < cutoff:
            continue

        # 구글 뉴스 제목은 "제목 - 언론사" 형태다. 뒤쪽을 떼어낸다.
        if title.endswith(f"- {source}"):
            title = title[: -len(source) - 2].strip()

        articles.append({
            "title": title,
            "source": source,
            "link": link,
            "published": published.astimezone(KST).strftime("%m.%d %H:%M"),
            "query": query,
        })
        if len(articles) >= limit:
            break

    return articles


def _dedupe(articles):
    """여러 검색어에서 같은 기사가 겹쳐 들어온 것을 걸러낸다."""
    seen, unique = set(), []
    for a in articles:
        key = re.sub(r"[^가-힣a-zA-Z0-9]", "", a["title"])[:30]
        if key and key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


def stock_news(code, hours=24):
    """종목 하나에 관한 뉴스."""
    articles = []
    for keyword in config.STOCKS[code]["keywords"]:
        articles.extend(search(keyword, hours=hours))
    return _dedupe(articles)


def macro_news(hours=24):
    """시장 전체를 흔드는 거시 이슈 뉴스."""
    articles = []
    for keyword in config.MACRO_KEYWORDS:
        articles.extend(search(keyword, hours=hours, limit=8))
    return _dedupe(articles)


if __name__ == "__main__":
    print("[거시 뉴스]")
    macro = macro_news()
    for a in macro[:12]:
        print(f"  {a['published']}  {a['title'][:52]:<52} ({a['source']})")
    print(f"  ... 총 {len(macro)}건")

    for code, info in config.STOCKS.items():
        print(f"\n[{info['name']}]")
        news = stock_news(code)
        for a in news[:8]:
            print(f"  {a['published']}  {a['title'][:52]:<52} ({a['source']})")
        print(f"  ... 총 {len(news)}건")
