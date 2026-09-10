"""카드 배경 사진을 창고에서 꺼내 준다.

매일 인터넷에서 사진을 검색해 오는 방식은 접었다. 검색은 자주 엉뚱한 걸 물어온다.
'semiconductor clean room' 에 거실 사진이, 'wall street sign' 에 스페인 도로표지판이,
'silicon wafer manufacturing' 에 바나나 디저트가 온 적이 있다.

지금은 주제별로 미리 골라 둔 사진을 assets/library/ 에 두고 거기서 꺼낸다.

  - 인터넷도 API 키도 필요 없다. 아침에 네트워크가 말썽이어도 사진은 나온다
  - 눈으로 확인하고 넣은 사진이라 엉뚱한 게 나갈 일이 없다
  - 주제마다 여러 장을 두고 날마다 돌려 쓰므로 같은 그림이 반복되지 않는다

창고를 새로 만들거나 마음에 안 드는 주제를 바꾸려면 build_photo_library.py 를 쓴다.
이 파일에 남아 있는 검색 함수들은 그 도구가 쓰는 것이고, 운영 중에는 불리지 않는다.
"""

import json
import re
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageStat

LIBRARY = Path(__file__).parent / "assets" / "library"
FALLBACK_DIR = Path(__file__).parent / "assets"
UA = "MorningReport/0.1"

SIZE = 720
MIN_WIDTH, MIN_HEIGHT = 900, 600

_index = None


# ── 창고에서 꺼내기 (운영 중에 쓰는 부분) ───────────────────────

def index():
    """주제 목록과 각 주제의 사진 파일 이름."""
    global _index
    if _index is None:
        path = LIBRARY / "index.json"
        _index = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _index


def topics():
    """카드가 고를 수 있는 주제 이름들."""
    return sorted(index().keys())


def pick(topic, seed=0):
    """주제에 맞는 사진 한 장을 고른다.

    seed 에 날짜와 카드 번호를 섞어 넣으면 같은 주제라도 날마다,
    카드마다 다른 사진이 나온다.
    """
    items = index().get(topic) or []
    if not items:
        return FALLBACK_DIR / "cover.jpg", {"topic": topic, "found": False}
    chosen = items[seed % len(items)]
    return LIBRARY / topic / chosen["file"], {"topic": topic, "found": True}


# ── 인터넷에서 찾기 (창고를 만들 때만 쓰는 부분) ────────────────

def _get(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as res:
        return res.read()


def _pixabay_call(query, api_key, limit):
    params = urllib.parse.urlencode({
        "key": api_key,
        "q": query,
        "image_type": "photo",
        "orientation": "horizontal",
        "min_width": MIN_WIDTH,
        "min_height": MIN_HEIGHT,
        "safesearch": "true",
        "order": "popular",
        "per_page": limit,
    })
    try:
        data = json.loads(_get(f"https://pixabay.com/api/?{params}"))
    except Exception as e:
        print(f"  [사진] Pixabay 검색 실패 ({query}): {e}")
        return []

    return [{
        "title": hit.get("tags", ""),
        "url": hit.get("largeImageURL") or hit.get("webformatURL"),
        "artist": hit.get("user", ""),
    } for hit in data.get("hits", []) if hit.get("largeImageURL")]


def _score(hit, words):
    """검색어의 낱말 중 몇 개가 사진 태그에 실제로 들어 있는지 센다.

    Pixabay 는 낱말이 다 맞는 사진이 없으면 상관없는 사진을 그냥 내준다.
    한 낱말만 맞아도 통과시키면 'floor' 하나로 나무 바닥 사진이,
    'terminal' 하나로 기차역 사진이 들어온다. 두 개 이상 맞아야 인정한다.
    """
    tags = hit.get("title", "").lower()
    return sum(1 for word in words if word in tags)


def _pixabay(query, api_key, limit=12):
    """낱말을 줄여 가며 실제로 관련 있는 사진을 찾는다."""
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 2]
    if not words:
        return []

    need = 2 if len(words) >= 2 else 1
    tries = [(query, need), (" ".join(words[:2]), need), (words[0], 1)]
    seen = set()

    for attempt, minimum in tries:
        if attempt in seen:
            continue
        seen.add(attempt)
        scored = [(_score(hit, words), hit) for hit in _pixabay_call(attempt, api_key, limit)]
        good = [hit for score, hit in sorted(scored, key=lambda x: -x[0]) if score >= minimum]
        if good:
            return good
    return []


def _is_flat_graphic(image):
    """도표나 문서 스캔을 걸러낸다.

    그래프는 배경이 한 가지 색으로 넓게 깔린다. 사진은 하늘이나 벽처럼
    단조로워 보이는 곳도 밝기가 계속 미세하게 달라진다.
    """
    small = image.convert("RGB").resize((64, 64))
    colors = small.getcolors(64 * 64)
    if not colors:
        return False
    return max(count for count, _ in colors) / float(64 * 64) > 0.20


def _colorfulness(image):
    small = image.convert("RGB").resize((64, 64))
    return ImageStat.Stat(small.convert("HSV").split()[1]).mean[0]


def _crop_square(image):
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS)


def download_image(url):
    return Image.open(BytesIO(_get(url))).convert("RGB")


if __name__ == "__main__":
    data = index()
    if not data:
        print("창고가 비어 있습니다. build_photo_library.py 를 먼저 실행하세요.")
    else:
        total = sum(len(v) for v in data.values())
        print(f"주제 {len(data)}개, 사진 {total}장")
        for topic in topics():
            print(f"  {topic:<15} {len(data[topic])}장")
