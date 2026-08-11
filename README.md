# THE DESK — AI 리서치 데스크 (웹앱)

TradingView 차트 + 애널리스트 4인(Taro/Smith/Nova/Kirk) + 리서치팀 + 수석 트레이더 Ace로
구성된 AI 주식 리서치 웹사이트입니다. 티커를 입력하면 각 애널리스트의 분석이 실시간으로
"데스크에 불이 켜지듯" 채워지고, 마지막에 Ace가 최종 판단을 내립니다.

## 설치 & 실행

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# .env에 본인의 GEMINI_API_KEY 입력 (https://aistudio.google.com/apikey 에서 무료 발급)

uvicorn main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000` 접속.

## 구조

```
backend/
  main.py              FastAPI 서버, /api/analyze SSE 스트리밍 엔드포인트
  config.py             API 키/설정
  data_sources.py       가격/재무/뉴스/커뮤니티 데이터 수집 (yfinance, Reddit, 네이버)
  llm_client.py         Gemini API 호출 래퍼
  agents/
    analysts.py           Taro/Smith/Nova/Kirk
    research_team.py       bull/bear 종합
    chief_trader.py         Ace 최종 판단
frontend/
  index.html            페이지 구조
  style.css              디자인 (다크 트레이딩 데스크 테마)
  app.js                  TradingView 위젯 + SSE 연결 + UI 업데이트
```

## 동작 흐름

1. 티커 입력 → `/api/analyze?ticker=...` 에 SSE(Server-Sent Events) 연결
2. 4명의 애널리스트가 각자 스레드에서 병렬로 데이터 수집 + Gemini 분석 → 완료되는 대로
   `event: analyst` 로 하나씩 전송 → 해당 데스크 카드에 실시간 반영
3. 4명 결과가 모이면 리서치팀이 종합 → `event: research`
4. Ace가 최종 buy/sell/hold 판단 → `event: decision`
5. `event: done` 으로 스트림 종료

## TradingView 차트

`https://s3.tradingview.com/tv.js` 무료 위젯을 사용합니다 (별도 API 키 불필요).
티커 → TradingView 심볼 변환 규칙:
- 6자리 숫자 또는 `.KS`/`.KQ` → `KRX:종목코드`
- 그 외(미국 등)는 입력 그대로 사용 — TradingView가 주요 거래소로 자동 해석

정확한 거래소를 지정하고 싶으면 `NASDAQ:AAPL`처럼 직접 입력해도 됩니다.

## 알려진 한계 & 확장 포인트

- **Kirk(커뮤니티)**: 네이버 종목토론실 스크래핑은 구조 변경 시 깨질 수 있습니다.
- **Reddit 검색**: 비인증 공개 엔드포인트라 레이트리밋 가능성이 있습니다. 본격 운영 시 PRAW+API 키 권장.
- **뉴스**: 현재 yfinance 기본 뉴스만 사용. NewsAPI/네이버 뉴스 API 추가 시 더 풍부해집니다.
- **배포**: 지금은 로컬 실행 기준입니다. 외부에 공개하려면 HTTPS, 인증, 레이트리밋을 추가하세요.
- **자동매매 없음**: Ace의 판단은 참고용이며 실제 주문 실행 로직은 포함되어 있지 않습니다.

## 주의사항

이 웹사이트가 만들어내는 결과는 투자 자문이 아닌 AI 기반 참고 리서치입니다.
최종 투자 결정과 그 책임은 본인에게 있습니다.
