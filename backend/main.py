"""
FastAPI 백엔드.
- GET /api/analyze?ticker=AAPL  → SSE로 애널리스트/리서치팀/Ace 결과를 순서대로 스트리밍
- 정적 프론트엔드(frontend/) 서빙
"""
import json
import asyncio
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from agents.analysts import ALL_ANALYSTS
from agents.research_team import ResearchTeam
from agents.chief_trader import Ace
from data_sources import normalize_ticker

app = FastAPI(title="AI Trading Desk")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def event_stream(ticker: str):
    ticker = normalize_ticker(ticker)
    yield sse("meta", {"ticker": ticker})

    order = {a.name: i for i, a in enumerate(ALL_ANALYSTS)}
    results = []

    # 각 애널리스트를 스레드로 병렬 실행하고, 완료되는 대로 이벤트 전송
    tasks = [asyncio.create_task(asyncio.to_thread(_safe_analyze, a, ticker)) for a in ALL_ANALYSTS]
    for task in asyncio.as_completed(tasks):
        result = await task
        results.append(result)
        yield sse("analyst", result)

    results.sort(key=lambda r: order.get(r.get("analyst"), 99))

    try:
        research_note = await asyncio.to_thread(ResearchTeam().synthesize, ticker, results)
    except Exception as e:
        research_note = {"overall_stance": "mixed", "conviction": 0, "bull_case": [], "bear_case": [],
                          "key_disagreements": "", "summary": f"리서치팀 종합 실패: {e}"}
    yield sse("research", research_note)

    try:
        final_decision = await asyncio.to_thread(Ace().decide, ticker, research_note)
    except Exception as e:
        final_decision = {"decision": "hold", "conviction": 0, "suggested_position_size_pct": 0,
                           "reasoning": f"최종 판단 실패: {e}", "key_risks": [], "invalidation_condition": "",
                           "disclaimer": "이 결과는 AI 기반 참고용 리서치이며 투자 자문이 아닙니다."}
    yield sse("decision", final_decision)

    yield sse("done", {})


def _safe_analyze(analyst, ticker):
    try:
        return analyst.analyze(ticker)
    except Exception as e:
        return {"analyst": analyst.name, "view": "neutral", "confidence": 0,
                "summary": f"분석 실패: {e}", "key_points": []}


@app.get("/api/analyze")
async def analyze(ticker: str = Query(...)):
    return StreamingResponse(event_stream(ticker), media_type="text/event-stream")


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
