"""
데이터 수집 모듈
- 기술적 분석용 가격 데이터 (yfinance)
- 기본적 분석용 재무 데이터 (yfinance)
- 뉴스 데이터 (yfinance)
- 커뮤니티 데이터 (Reddit 공개 API / 네이버 종목토론실 - 확장 가능한 스텁)
"""
import requests
import pandas as pd
import numpy as np
import yfinance as yf

from config import REDDIT_SUBREDDITS

HEADERS = {"User-Agent": "ai-trading-firm/1.0"}


def normalize_ticker(ticker: str) -> str:
    """한국 6자리 숫자 티커면 .KS(코스피)를 기본으로 붙여준다.
    코스닥 종목은 사용자가 직접 '.KQ'를 붙여서 입력해야 정확하다."""
    t = ticker.strip().upper()
    if t.isdigit() and len(t) == 6:
        return f"{t}.KS"
    return t


def is_korean_ticker(ticker: str) -> bool:
    return ticker.upper().endswith((".KS", ".KQ"))


# ---------------------------------------------------------------------------
# Taro (기술적 분석)용 데이터
# ---------------------------------------------------------------------------
def get_technical_data(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    hist = tk.history(period="6mo")
    if hist.empty:
        return {"error": f"'{ticker}' 가격 데이터를 가져올 수 없습니다."}

    close = hist["Close"]
    sma20 = close.rolling(20).mean()
    sma60 = close.rolling(60).mean()

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    last_close = float(close.iloc[-1])
    price_1m_ago = float(close.iloc[-21]) if len(close) > 21 else float(close.iloc[0])
    price_change_1m = (last_close / price_1m_ago - 1) * 100

    avg_vol_20 = float(hist["Volume"].tail(20).mean())
    latest_vol = float(hist["Volume"].iloc[-1])

    return {
        "ticker": ticker,
        "last_close": round(last_close, 2),
        "sma20": round(float(sma20.iloc[-1]), 2) if not pd.isna(sma20.iloc[-1]) else None,
        "sma60": round(float(sma60.iloc[-1]), 2) if not pd.isna(sma60.iloc[-1]) else None,
        "rsi14": round(float(rsi.iloc[-1]), 1) if not pd.isna(rsi.iloc[-1]) else None,
        "macd": round(float(macd.iloc[-1]), 3) if not pd.isna(macd.iloc[-1]) else None,
        "macd_signal": round(float(signal.iloc[-1]), 3) if not pd.isna(signal.iloc[-1]) else None,
        "price_change_1m_pct": round(price_change_1m, 2),
        "52w_high": round(float(hist["Close"].max()), 2),
        "52w_low": round(float(hist["Close"].min()), 2),
        "volume_vs_20d_avg_pct": round((latest_vol / avg_vol_20 - 1) * 100, 1) if avg_vol_20 else None,
    }


# ---------------------------------------------------------------------------
# Smith (기본적 분석)용 데이터
# ---------------------------------------------------------------------------
def get_fundamental_data(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    try:
        info = tk.info
    except Exception as e:
        return {"error": f"펀더멘털 데이터 조회 실패: {e}"}

    if not info:
        return {"error": f"'{ticker}' 펀더멘털 데이터가 없습니다."}

    fields = [
        "shortName", "sector", "industry", "marketCap",
        "trailingPE", "forwardPE", "priceToBook",
        "returnOnEquity", "returnOnAssets", "debtToEquity",
        "revenueGrowth", "earningsGrowth", "grossMargins",
        "operatingMargins", "profitMargins", "dividendYield",
        "freeCashflow", "totalCash", "totalDebt",
    ]
    return {k: info.get(k) for k in fields}


# ---------------------------------------------------------------------------
# Nova (뉴스 분석)용 데이터
# ---------------------------------------------------------------------------
def get_news(ticker: str, limit: int = 8) -> list:
    tk = yf.Ticker(ticker)
    try:
        news = tk.news or []
    except Exception:
        news = []

    results = []
    for item in news[:limit]:
        content = item.get("content", item)  # yfinance 최신 버전은 content 안에 중첩
        title = content.get("title") or item.get("title")
        publisher = (content.get("provider") or {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher")
        link = (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link")
        pub_date = content.get("pubDate") or item.get("providerPublishTime")
        if title:
            results.append({"title": title, "publisher": publisher, "link": link, "published": pub_date})
    return results


# ---------------------------------------------------------------------------
# Kirk (커뮤니티 분석)용 데이터
# ---------------------------------------------------------------------------
def get_community_sentiment(ticker: str, company_name: str = "") -> list:
    """한국 종목은 네이버 종목토론실 스크래핑, 미국 종목은 Reddit 공개 검색 API 사용.
    실패하거나 데이터가 없으면 빈 리스트를 반환하고 상위 로직에서 처리한다."""
    if is_korean_ticker(ticker):
        return _get_naver_discussion(ticker)
    return _get_reddit_mentions(ticker, company_name)


def _get_reddit_mentions(ticker: str, company_name: str) -> list:
    query = ticker.replace(".KS", "").replace(".KQ", "")
    posts = []
    for sub in REDDIT_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {"q": query, "restrict_sr": 1, "sort": "new", "limit": 5, "t": "week"}
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=8)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for child in data.get("data", {}).get("children", []):
                d = child.get("data", {})
                posts.append({
                    "subreddit": sub,
                    "title": d.get("title"),
                    "score": d.get("score"),
                    "num_comments": d.get("num_comments"),
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                })
        except Exception:
            continue
    return posts


def _get_naver_discussion(ticker: str) -> list:
    """네이버 종목토론실 최신 글 제목 스크래핑 (간이 버전).
    구조 변경 시 실패할 수 있으므로 실패하면 빈 리스트를 반환한다."""
    code = ticker.replace(".KS", "").replace(".KQ", "")
    url = f"https://finance.naver.com/item/board.naver?code={code}"
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table.type2 tr")
        posts = []
        for row in rows:
            title_tag = row.select_one("td.title a")
            if title_tag:
                posts.append({"title": title_tag.get_text(strip=True), "url": "https://finance.naver.com" + title_tag.get("href", "")})
            if len(posts) >= 15:
                break
        return posts
    except Exception:
        return []
