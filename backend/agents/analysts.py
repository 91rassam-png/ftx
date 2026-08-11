"""
애널리스트 4명:
- Taro: 차트 기반 기술적 분석
- Smith: 기업가치 기반 기본적 분석
- Nova: 뉴스 분석
- Kirk: 커뮤니티(투자자 심리) 분석

각 애널리스트는 데이터를 수집하고, Claude에게 자신의 전문 분야 관점에서
{view, confidence, summary, key_points} 형태의 JSON 분석을 받아온다.
"""
import json

from llm_client import ask_llm_json
import data_sources as ds

RESPONSE_SCHEMA_NOTE = """
출력은 다음 JSON 스키마를 정확히 따르라:
{
  "view": "bullish" | "bearish" | "neutral",
  "confidence": 0-100 사이의 정수 (자신의 판단에 대한 확신도),
  "summary": "2~3문장의 한국어 요약",
  "key_points": ["핵심 근거 1", "핵심 근거 2", "핵심 근거 3"]
}
"""


class BaseAnalyst:
    name = "Base"
    role_description = ""

    def gather_data(self, ticker: str, company_name: str = "") -> dict:
        raise NotImplementedError

    def system_prompt(self) -> str:
        return f"""너는 '{self.name}'라는 이름의 주식 애널리스트다.
전문 분야: {self.role_description}
너는 오직 이 전문 분야의 관점에서만 판단한다. 다른 분야는 참고만 하고 결론에 섞지 마라.
데이터가 부족하거나 신호가 불명확하면 솔직하게 neutral과 낮은 confidence를 줘라.
과장하지 말고, 데이터에 근거해서 냉정하게 판단하라.
{RESPONSE_SCHEMA_NOTE}"""

    def analyze(self, ticker: str, company_name: str = "") -> dict:
        data = self.gather_data(ticker, company_name)
        user_content = f"티커: {ticker}\n\n[수집된 데이터]\n{json.dumps(data, ensure_ascii=False, indent=2, default=str)}"
        result = ask_llm_json(self.system_prompt(), user_content)
        result["analyst"] = self.name
        result["raw_data"] = data
        return result


class Taro(BaseAnalyst):
    name = "Taro"
    role_description = "차트 기반 기술적 분석 (이동평균선, RSI, MACD, 거래량, 추세)"

    def gather_data(self, ticker: str, company_name: str = "") -> dict:
        return ds.get_technical_data(ticker)


class Smith(BaseAnalyst):
    name = "Smith"
    role_description = "기업가치 기반 기본적 분석 (PER, PBR, ROE, 성장성, 재무건전성)"

    def gather_data(self, ticker: str, company_name: str = "") -> dict:
        return ds.get_fundamental_data(ticker)


class Nova(BaseAnalyst):
    name = "Nova"
    role_description = "최신 뉴스 분석 (헤드라인 톤, 이벤트/촉매, 리스크 요인)"

    def gather_data(self, ticker: str, company_name: str = "") -> dict:
        return {"news": ds.get_news(ticker)}


class Kirk(BaseAnalyst):
    name = "Kirk"
    role_description = "커뮤니티/투자자 심리 분석 (게시판 반응, 관심도, 극단적 낙관/비관 신호)"

    def gather_data(self, ticker: str, company_name: str = "") -> dict:
        return ds.get_community_sentiment(ticker, company_name)


ALL_ANALYSTS = [Taro(), Smith(), Nova(), Kirk()]
