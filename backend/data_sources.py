"""
데이터 수집 모듈
- 기술적 분석용 가격 데이터 (yfinance)
- 기본적 분석용 재무 데이터 (yfinance)
- 뉴스 데이터 (yfinance)
- 커뮤니티 데이터 (StockTwits 공개 API + Reddit 공개 API / 네이버 종목토론실)

주의: Yahoo Finance는 python-requests의 TLS 지문을 감지해 클라우드 IP를
빈번히 차단한다 (특히 Render/Railway 같은 공유 IP 호스팅). curl_cffi로
브라우저 TLS 지문을 흉내내면 차단 빈도가 크게 줄어든다 (yfinance 공식 권장).
"""
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf

from config import REDDIT_SUBREDDITS

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _build_yf_session():
    """curl_cffi 세션을 만들어 브라우저 TLS 지문으로 위장한다.
    curl_cffi가 없거나 실패하면 None을 반환해 yfinance 기본 동작으로 폴백한다."""
    try:
        from curl_cffi import requests as curl_requests
        return curl_requests.Session(impersonate="chrome")
    except Exception:
        return None


_YF_SESSION = _build_yf_session()


def _get_ticker(ticker: str) -> yf.Ticker:
    if _YF_SESSION is not None:
        return yf.Ticker(ticker, session=_YF_SESSION)
    return yf.Ticker(ticker)


def _with_retry(fn, attempts: int = 3, base_delay: float = 1.5):
    """일시적인 429/네트워크 오류에 대비한 지수 백오프 재시도."""
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
    raise last_err


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
    try:
        tk = _get_ticker(ticker)
        hist = _with_retry(lambda: tk.history(period="6mo"))
    except Exception as e:
        return {"error": f"가격 데이터 조회 실패 (Yahoo Finance 차단/제한 가능성): {e}"}

    if hist is None or hist.empty:
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
    tk = _get_ticker(ticker)

    try:
        info = _with_retry(lambda: tk.info)
    except Exception as e:
        info = None
        info_error = str(e)
    else:
        info_error = None

    if info:
        fields = [
            "shortName", "sector", "industry", "marketCap",
            "trailingPE", "forwardPE", "priceToBook",
            "returnOnEquity", "returnOnAssets", "debtToEquity",
            "revenueGrowth", "earningsGrowth", "grossMargins",
            "operatingMargins", "profitMargins", "dividendYield",
            "freeCashflow", "totalCash", "totalDebt",
        ]
        return {k: info.get(k) for k in fields}

    # info 전체 조회가 막혔을 때: 더 가벼운 fast_info 엔드포인트로 최소한의 데이터라도 시도
    try:
        fast = tk.fast_info
        return {
            "note": "전체 재무정보(quoteSummary) 조회가 제한되어 축약된 fast_info만 사용함",
            "marketCap": getattr(fast, "market_cap", None),
            "last_price": getattr(fast, "last_price", None),
            "year_high": getattr(fast, "year_high", None),
            "year_low": getattr(fast, "year_low", None),
            "shares_outstanding": getattr(fast, "shares", None),
            "info_error": info_error,
        }
    except Exception as e:
        return {"error": f"펀더멘털 데이터 조회 실패 (Yahoo Finance 차단/제한 가능성): {info_error or e}"}


# ---------------------------------------------------------------------------
# Nova (뉴스 분석)용 데이터
# ---------------------------------------------------------------------------
def get_news(ticker: str, limit: int = 8) -> list:
    tk = _get_ticker(ticker)
    try:
        news = _with_retry(lambda: tk.news) or []
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
def get_community_sentiment(ticker: str, company_name: str = "") -> dict:
    """한국 종목은 네이버 종목토론실, 미국 종목은 StockTwits(주 소스) + Reddit(보조)을 사용한다.
    각 소스가 실패하면 이유를 함께 담아 반환해서, 상위 LLM이 '데이터가 없다'와
    '데이터가 원래 조용하다'를 구분할 수 있게 한다."""
    if is_korean_ticker(ticker):
        posts, error = _get_naver_discussion(ticker)
        return {"source": "naver_board", "posts": posts, "source_error": error}

    stocktwits_posts, st_error = _get_stocktwits_mentions(ticker)
    reddit_posts, reddit_error = _get_reddit_mentions(ticker, company_name)

    return {
        "source": "stocktwits+reddit",
        "stocktwits_posts": stocktwits_posts,
        "stocktwits_error": st_error,
        "reddit_posts": reddit_posts,
        "reddit_error": reddit_error,
    }


def _get_stocktwits_mentions(ticker: str, limit: int = 20):
    """StockTwits 공개 스트림 API (인증 불필요). 사용자가 직접 태그한
    bullish/bearish 감정까지 함께 내려줘서 Reddit보다 신호가 명확하다."""
    symbol = ticker.replace(".KS", "").replace(".KQ", "")
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return [], f"StockTwits HTTP {resp.status_code}"
        data = resp.json()
        posts = []
        for m in (data.get("messages") or [])[:limit]:
            sentiment = None
            entities = m.get("entities") or {}
            sent_obj = entities.get("sentiment")
            if sent_obj:
                sentiment = sent_obj.get("basic")  # "Bullish" | "Bearish"
            posts.append({
                "body": (m.get("body") or "")[:300],
                "sentiment": sentiment,
                "likes": (m.get("likes") or {}).get("total", 0),
            })
        return posts, None
    except Exception as e:
        return [], f"StockTwits 요청 실패: {e}"


def _get_reddit_mentions(ticker: str, company_name: str):
    query = ticker.replace(".KS", "").replace(".KQ", "")
    posts = []
    errors = []
    for sub in REDDIT_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {"q": query, "restrict_sr": 1, "sort": "new", "limit": 5, "t": "week"}
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=8)
            if resp.status_code != 200:
                errors.append(f"r/{sub} HTTP {resp.status_code}")
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
        except Exception as e:
            errors.append(f"r/{sub} 요청 실패: {e}")
    return posts, ("; ".join(errors) if errors and not posts else None)


def _get_naver_discussion(ticker: str):
    """네이버 종목토론실 최신 글 제목 스크래핑 (간이 버전).
    구조 변경 시 실패할 수 있으므로 실패하면 빈 리스트 + 에러 사유를 반환한다."""
    code = ticker.replace(".KS", "").replace(".KQ", "")
    url = f"https://finance.naver.com/item/board.naver?code={code}"
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return [], f"네이버 종목토론실 HTTP {resp.status_code}"
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
        if not posts:
            return [], "게시글을 찾지 못함 (페이지 구조 변경 가능성)"
        return posts, None
    except Exception as e:
        return [], f"네이버 종목토론실 요청 실패: {e}"
