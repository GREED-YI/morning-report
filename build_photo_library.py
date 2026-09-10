"""배경 사진 창고를 만든다. 딱 한 번만 돌리는 도구다.

매일 사진을 검색해서 쓰는 방식은 접었다. 검색은 자주 엉뚱한 걸 물어온다.
'semiconductor clean room' 에 거실 사진이, 'wall street bull' 에 인도의 소가 왔다.

대신 주제별로 쓸 만한 사진을 미리 모아 창고에 넣어 둔다. 운영할 때는
카드가 주제 이름만 고르고, 창고에서 그날 것을 꺼내 쓴다. 그러면
  - 인터넷도 API 키도 필요 없고
  - 엉뚱한 사진이 나갈 일이 없고
  - 주제마다 여러 장을 두면 날마다 다른 그림이 나간다.

    python build_photo_library.py            사진 후보 내려받기
    python build_photo_library.py --sheet    확인용 대조표 만들기
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import kakaolib
import photos

LIBRARY = Path(__file__).parent / "assets" / "library"

# 주제마다 검색어를 여러 개 둔다. 한 검색어에서 안 나오면 다음 것으로 넘어간다.
TOPICS = {
    "oil": ["oil refinery night", "oil refinery", "oil pump jack"],
    "centralbank": ["capitol washington building", "government building columns", "parliament architecture"],
    "geopolitics": ["cargo ship sea", "container ship port", "navy ship"],
    "semiconductor": ["semiconductor chip", "circuit board macro", "microchip"],
    "datacenter": ["data center server", "server room", "network cables"],
    # 'wall street sign' 은 sign 만 맞은 낙서·도로표지판을 물어왔다.
    # 건물이나 화면처럼 덩어리가 큰 사물을 가리키는 말이 안전하다.
    "trading": ["stock market chart", "financial chart screen", "trading monitors"],
    "exchange": ["new york stock exchange", "skyscraper finance city", "office towers city"],
    "currency": ["dollar banknotes", "korean won money", "banknotes closeup"],
    "seoul": ["seoul night", "seoul city", "korea city night"],
    "factory": ["factory production line", "industrial factory", "assembly line"],
    # 특정 회사 제품이 크게 나오면 안 된다. 남의 회사 카드에 애플 기기가
    # 깔리는 사고가 있었다. 부품이나 생산 현장처럼 상표가 없는 장면을 고른다.
    "electronics": ["computer motherboard", "electronic parts", "hardware components"],
    "schedule": ["calendar desk", "clock office", "planner notebook"],
    "sunrise": ["sunrise city", "morning sky city", "dawn skyline"],
    "checklist": ["checklist notebook pen", "notebook pen desk", "writing notes"],
}

PER_TOPIC = 4


def download():
    api_key = kakaolib.load_env().get("PIXABAY_API_KEY", "")
    if not api_key:
        raise SystemExit(
            ".env 에 PIXABAY_API_KEY 가 필요합니다.\n"
            "  창고를 만들 때만 쓰고, 만든 뒤에는 필요 없습니다."
        )

    LIBRARY.mkdir(parents=True, exist_ok=True)
    index_path = LIBRARY / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    # --only 뒤에 주제 이름을 적으면 그것만 다시 받는다. 마음에 안 드는 주제만 손볼 때 쓴다.
    wanted = TOPICS
    if "--only" in sys.argv:
        names = sys.argv[sys.argv.index("--only") + 1].split(",")
        wanted = {k: v for k, v in TOPICS.items() if k in names}

    for topic, queries in wanted.items():
        folder = LIBRARY / topic
        folder.mkdir(exist_ok=True)
        saved, used_urls = [], set()

        for query in queries:
            if len(saved) >= PER_TOPIC:
                break
            for hit in photos._pixabay(query, api_key, limit=12):
                if len(saved) >= PER_TOPIC:
                    break
                if hit["url"] in used_urls:
                    continue
                used_urls.add(hit["url"])
                name = f"{len(saved) + 1}.jpg"
                try:
                    image = Image.open(
                        __import__("io").BytesIO(photos._get(hit["url"]))
                    ).convert("RGB")
                except Exception:
                    continue
                if photos._is_flat_graphic(image):
                    continue
                photos._crop_square(image).save(folder / name, "JPEG", quality=78)
                saved.append({"file": name, "query": query, "tags": hit["title"][:70]})

        index[topic] = saved
        print(f"{topic:<15} {len(saved)}장")

    index = {topic: index[topic] for topic in TOPICS if topic in index}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n창고: {LIBRARY}")


def sheet(out_path="library_sheet.png"):
    """주제별 사진을 한 장에 모아 눈으로 확인할 수 있게 한다."""
    index = json.loads((LIBRARY / "index.json").read_text(encoding="utf-8"))
    cell, gap, label = 190, 4, 22
    rows = len(index)
    sheet_image = Image.new(
        "RGB",
        (140 + PER_TOPIC * (cell + gap), rows * (cell + gap + label)),
        "#101418",
    )
    draw = ImageDraw.Draw(sheet_image)

    for r, (topic, items) in enumerate(index.items()):
        y = r * (cell + gap + label)
        draw.text((8, y + cell // 2), topic, fill="#8CC3FF")
        for c, item in enumerate(items):
            x = 140 + c * (cell + gap)
            sheet_image.paste(
                Image.open(LIBRARY / topic / item["file"]).resize((cell, cell)), (x, y)
            )
            draw.text((x + 3, y + cell + 4), item["tags"][:28], fill="#9AA5B1")

    sheet_image.save(out_path, "PNG")
    print(out_path)


if __name__ == "__main__":
    if "--sheet" in sys.argv:
        sheet(sys.argv[-1] if sys.argv[-1].endswith(".png") else "library_sheet.png")
    else:
        download()
