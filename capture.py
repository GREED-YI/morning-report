"""카드 한 장을 PNG 로 찍는다. 카카오톡 메시지의 대표 이미지로 쓴다.

브라우저를 화면 없이 띄워서 캡처 페이지를 열고 사진을 찍는 방식이다.
400x400 짜리 카드를 배율 2배로 찍어 800x800 을 만든다.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent / "out"


def capture(html_path, png_name="card.png", size=400, scale=2):
    """캡처 페이지를 열어 PNG 로 저장하고 그 경로를 돌려준다."""
    OUT_DIR.mkdir(exist_ok=True)
    png_path = OUT_DIR / png_name

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": size, "height": size},
            device_scale_factor=scale,
        )
        page.goto(Path(html_path).as_uri())
        # 웹폰트가 다 내려온 뒤에 찍어야 글씨가 깨지지 않는다
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(png_path))
        browser.close()

    return png_path


def capture_full(html_path, png_name="preview.png", width=430):
    """카드뉴스 페이지 전체를 폰 너비로 찍는다. 디자인 확인용이다."""
    OUT_DIR.mkdir(exist_ok=True)
    png_path = OUT_DIR / png_name

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(Path(html_path).as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(png_path), full_page=True)
        browser.close()

    return png_path


if __name__ == "__main__":
    path = capture(OUT_DIR / "capture.html")
    print(f"저장 완료: {path}  ({path.stat().st_size / 1024:.0f} KB)")
