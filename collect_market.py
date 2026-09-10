"""시세 수집. 카드에 들어가는 숫자는 전부 여기서 나온다.

원칙: 숫자는 AI 가 만들지 않는다.
Claude 는 문장만 쓰고, 종가·등락률 같은 값은 이 파일이 직접 가져온다.
그래야 없는 숫자를 지어내는 일이 구조적으로 불가능해진다.

데이터는 야후 파이낸스 한 곳에서 받는다. 국내 종목도 `000660.KS` 처럼
뒤에 시장 코드를 붙이면 조회된다. 가입도 키도 필요 없다.

한때 pykrx 를 쓰려 했으나 최신 버전이 한국거래소 계정 로그인을 요구해서 접었다.
그 대가로 외국인·기관 순매수는 못 가져온다. 필요해지면 공공데이터포털의
금융위원회 API 를 붙이면 되는데, 그때는 별도 가입이 필요하다.
"""

from datetime import datetime, timedelta, timezone

import yfinance as yf

import config

KST = timezone(timedelta(hours=9))


def _history(ticker, days=15):
    """티커 하나의 최근 종가 흐름을 가져온다."""
    hist = yf.Ticker(ticker).history(period=f"{days}d", auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"{ticker} 시세를 가져오지 못했습니다.")
    return hist


def _change(closes):
    """마지막 종가와 그 전 종가로 등락을 계산한다."""
    last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
    return {
        "close": last,
        "prev": prev,
        "change": last - prev,
        "change_pct": round((last - prev) / prev * 100, 2),
    }


def _direction(pct):
    return "up" if pct > 0 else ("down" if pct < 0 else "flat")


# ── 국내 종목 ───────────────────────────────────────────────────

def korean_stock(code):
    """종목 하나의 전일 시세와 최근 닷새 흐름."""
    info = config.STOCKS[code]
    hist = _history(info["ticker"])
    closes = hist["Close"].dropna()
    volumes = hist["Volume"].dropna()
    q = _change(closes)

    # 거래대금은 거래량 x 종가로 어림한다. 실제로는 체결 평균가로 계산하므로
    # 값이 조금 다르다. 카드에는 "약" 을 붙여 표시한다.
    approx_value = float(volumes.iloc[-1]) * q["close"]

    trend = [
        {"date": idx.strftime("%m.%d"), "close": int(close)}
        for idx, close in closes.tail(5).items()
    ]

    return {
        "code": code,
        "name": info["name"],
        "date": closes.index[-1].strftime("%Y-%m-%d"),
        "close": int(q["close"]),
        "change_pct": q["change_pct"],
        "direction": _direction(q["change_pct"]),
        "volume": int(volumes.iloc[-1]),
        "approx_value_krw": int(approx_value),
        "trend": trend,
        "peer_rows": peers(info["peers"]),
    }


# ── 밤새 지표 ───────────────────────────────────────────────────

def _format(label, kind, q):
    """지표 종류에 맞게 사람이 읽을 문자열을 만든다."""
    pct = q["change_pct"]
    if kind == "price_pct":
        value = f"{q['close']:,.2f} ({pct:+.2f}%)"
    elif kind == "rate":
        value = f"{q['close']:.2f}% ({q['change']:+.2f}p)"
    elif kind == "level_pct":
        value = f"{q['close']:.1f} ({pct:+.1f}%)"
    else:
        value = f"{pct:+.2f}%"
    return {
        "label": label,
        "value": value,
        "change_pct": pct,
        "direction": _direction(pct),
    }


def overnight():
    """밤새 미국장 지표. 하나가 빠져도 브리핑은 나가야 하므로 개별로 감싼다."""
    rows = []
    for ticker, label, kind in config.MARKET_INDICATORS:
        try:
            rows.append(_format(label, kind, _change(_history(ticker)["Close"].dropna())))
        except Exception:
            continue
    return rows


def peers(tickers):
    """종목과 같이 움직이는 미국 종목의 야간 등락."""
    rows = []
    for ticker in tickers:
        try:
            q = _change(_history(ticker)["Close"].dropna())
            rows.append({
                "ticker": ticker,
                "change_pct": q["change_pct"],
                "direction": _direction(q["change_pct"]),
            })
        except Exception:
            continue
    return rows


# ── 확인용 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[밤새 지표]")
    for row in overnight():
        print(f"  {row['label']:<14} {row['value']:>22}  {row['direction']}")

    for code, info in config.STOCKS.items():
        data = korean_stock(code)
        print(f"\n[{data['name']}]  기준일 {data['date']}")
        print(f"  종가       {data['close']:>12,} 원  ({data['change_pct']:+.2f}%)")
        print(f"  거래대금   약 {data['approx_value_krw'] / 1e12:>9.1f} 조원")
        print(f"  닷새 흐름  " + " → ".join(f"{t['close']:,}" for t in data["trend"]))
        print(f"  동행 종목  {peers(info['peers'])}")
