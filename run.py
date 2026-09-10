"""아침 브리핑을 처음부터 끝까지 한 번에 만든다.

    python run.py            평소 실행
    python run.py --force    휴장일이어도 강제로 만든다 (시험용)

순서는 이렇다.
    1 수집   시세와 뉴스를 모은다
    2 요약   카드에 들어갈 문장을 만든다
    3 조립   숫자와 문장을 합쳐 카드 목록을 만든다
    4 렌더   웹페이지와 카톡용 대표 이미지를 만든다

발송은 아직 붙이지 않았다. 만들어진 결과를 눈으로 확인한 뒤에 붙인다.
"""

import json
import sys
import traceback
from datetime import datetime, timedelta, timezone

import assemble
import capture
import collect_market
import config
import providers
import render
import send
import summarize

KST = timezone(timedelta(hours=9))


def is_holiday():
    """오늘 국내 증시가 쉬는지 본다.

    주말은 확실하다. 공휴일은 야후에서 받은 최근 종가의 날짜로 짐작한다.
    어제나 오늘 종가가 없으면 장이 안 열린 것으로 본다.
    """
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return True, "주말"

    first = next(iter(config.STOCKS))
    last_date = collect_market.korean_stock(first)["date"]
    days_old = (now.date() - datetime.strptime(last_date, "%Y-%m-%d").date()).days
    if days_old > 3:
        return True, f"최근 거래일이 {last_date} 로 오래됐다"
    return False, ""


def main():
    force = "--force" in sys.argv
    started = datetime.now(KST)
    print(f"모닝 리포트 생성 시작  {started:%Y-%m-%d %H:%M} KST")

    holiday, reason = is_holiday()
    if holiday and not force:
        print(f"오늘은 장이 열리지 않습니다 ({reason}). 발송을 건너뜁니다.")
        return 0
    if holiday:
        print(f"휴장일이지만 --force 라서 계속합니다 ({reason})")

    codes = list(config.STOCKS.keys())

    print("\n[1/5] 시세 수집")
    overnight = collect_market.overnight()
    stocks = {code: collect_market.korean_stock(code) for code in codes}
    print(f"  지표 {len(overnight)}개, 종목 {len(stocks)}개")

    saved = render.OUT_DIR / "texts.json"

    if "--reuse" in sys.argv and saved.exists():
        # 지난번에 만든 문장을 그대로 쓴다. 디자인이나 발송만 손볼 때
        # 모델을 다시 부르지 않으려는 것이다. 무료 한도도 아낀다.
        print("\n[2/5] 지난번 문장 재사용 (--reuse)")
        texts = json.loads(saved.read_text(encoding="utf-8"))
    else:
        print("\n[2/5] 카드 문장 생성")
        try:
            texts = summarize.build_texts(codes, overnight, stocks)
        except providers.ProviderError as e:
            print(f"\n실패: {e}")
            return 1

        # 모델이 뭘 썼는지 나중에 들여다볼 수 있게 남겨 둔다.
        # 카드가 이상하게 나왔을 때 프롬프트 문제인지 렌더링 문제인지 여기서 갈린다.
        render.OUT_DIR.mkdir(exist_ok=True)
        saved.write_text(json.dumps(texts, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[3/5] 카드 조립")
    report = assemble.build_report(texts, overnight, stocks, codes)
    total = sum(len(s["cards"]) for s in report["sections"])
    print(f"  카드 {total}장")

    print("\n[4/5] 페이지와 이미지 생성")
    page = render.write_page(report, "index.html")
    capture_page = render.write_capture_page(report)
    png = capture.capture(capture_page, "card.png")

    print(f"  웹페이지    {page}")
    print(f"  대표 이미지 {png}  ({png.stat().st_size / 1024:.0f} KB)")

    if "--no-send" in sys.argv:
        print("\n--no-send 라서 발송은 건너뜁니다.")
    else:
        print("\n[5/5] 카카오톡 발송")
        try:
            send.send(report)
        except SystemExit as e:
            # 토큰이 없거나 만료된 경우. 만든 결과는 살아 있으므로 실패로 보지 않는다.
            print(f"  발송 실패: {e}")
            print("  step1_auth.py 로 다시 로그인한 뒤 --no-send 없이 실행하세요.")

    took = (datetime.now(KST) - started).total_seconds()
    print(f"\n완료 ({took:.0f}초)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n중단했습니다.")
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
