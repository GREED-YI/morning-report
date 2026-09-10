"""만들어진 브리핑을 카카오톡으로 보낸다.

보내는 모양은 두 가지다.

  피드    대표 이미지 한 장 + 요약 세 줄 + 버튼. 카드뉴스 주소가 있을 때 쓴다.
  텍스트  요약 세 줄만. 주소가 아직 없을 때 쓴다.

카카오는 메시지에 들어가는 이미지와 링크의 도메인을 앱에 미리 등록하도록
요구한다. config.SITE_URL 을 채우기 전에 그 도메인을 콘솔의
[앱 > 제품 링크 관리 > 웹 도메인] 에 등록해 두어야 버튼이 동작한다.
"""

import re

import config
import kakaolib


def _plain(text):
    """카드용 표기를 걷어내고 카톡에 들어갈 맨 글자로 만든다."""
    text = re.sub(r"<br\s*/?>", " ", str(text or ""))
    text = text.replace("\\n", " ").replace("\n", " ")
    text = re.sub(r"\[\[(.+?)\]\]", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def summary_lines(report):
    """카톡 본문에 넣을 세 줄. 마무리 카드의 '오늘 체크 3가지' 를 쓴다."""
    for section in report["sections"]:
        for card in section["cards"]:
            if card["type"] == "closing":
                marks = "①②③④⑤"
                return [
                    f"{marks[i] if i < len(marks) else '·'} {_plain(item)}"
                    for i, item in enumerate(card["items"][:3])
                ]
    return []


def headline(report):
    first = report["sections"][0]["cards"][0]
    return _plain(first["headline"])


def build_message(report, page_url="", image_url=""):
    """보낼 메시지를 만든다. 주소가 없으면 글자만 보내는 모양으로 돌아간다."""
    title = f"[모닝 리포트] {report['date']} ({report['weekday']})"
    body = "\n".join(summary_lines(report))
    total = sum(len(s["cards"]) for s in report["sections"])

    if not (page_url and image_url):
        return {
            "object_type": "text",
            "text": f"{title}\n\n{headline(report)}\n\n{body}",
            "link": {},
        }

    link = {"web_url": page_url, "mobile_web_url": page_url}
    return {
        "object_type": "feed",
        "content": {
            "title": headline(report),
            "description": body,
            "image_url": image_url,
            "image_width": 800,
            "image_height": 800,
            "link": link,
        },
        "buttons": [{"title": f"카드 {total}장 전체 보기", "link": link}],
    }


def send(report):
    """구독자에게 보낸다. 지금은 나에게 보내기라 한 명뿐이다."""
    env = kakaolib.load_env()

    page_url, image_url = "", ""
    if config.SITE_URL:
        base = config.SITE_URL.rstrip("/")
        page_url = f"{base}/"
        # 주소 뒤에 날짜를 붙여 카톡이 어제 이미지를 캐시해 두고 다시 쓰는 것을 막는다
        image_url = f"{base}/card.png?d={report['date']}"

    message = build_message(report, page_url, image_url)
    kakaolib.send_to_me(env, message)

    kind = "피드(이미지+버튼)" if message["object_type"] == "feed" else "텍스트"
    print(f"  카카오톡 발송 완료 · {kind}")
    if not config.SITE_URL:
        print("  config.SITE_URL 이 비어 있어 글자만 보냈습니다.")
    return message
