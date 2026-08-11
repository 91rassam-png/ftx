"""
리서치팀: Taro/Smith/Nova/Kirk 4명의 분석을 종합해서
bull(강세) / bear(약세) / mixed(혼재) 케이스를 정리한다.
최종 매매 결정은 내리지 않는다 (그건 Ace의 역할).
"""
import json
from llm_client import ask_llm_json

SYSTEM_PROMPT = """너는 리서치팀 팀장이다.
4명의 애널리스트(Taro=기술적분석, Smith=기본적분석, Nova=뉴스분석, Kirk=커뮤니티분석)의
분석 결과를 받아서 종합 리서치 노트를 작성한다.

규칙:
- 너는 최종 매매 결정을 내리지 않는다. 오직 bull/bear 논리를 정리하는 것이 역할이다.
- 4명의 의견이 갈리면 억지로 봉합하지 말고 '의견 불일치' 자체를 중요한 정보로 취급하라.
- 각 애널리스트 견해의 신뢰도(confidence)도 고려하라.

출력은 다음 JSON 스키마를 정확히 따르라 (설명, 코드블록 없이 순수 JSON만):
{
  "overall_stance": "bull" | "bear" | "mixed",
  "conviction": 0-100 사이의 정수,
  "bull_case": ["강세 논거 1", "강세 논거 2", ...],
  "bear_case": ["약세 논거 1", "약세 논거 2", ...],
  "key_disagreements": "애널리스트 간 의견이 갈리는 지점 설명 (없으면 빈 문자열)",
  "summary": "3~4문장의 종합 요약"
}
"""


class ResearchTeam:
    name = "Research Team"

    def synthesize(self, ticker: str, analyst_results: list) -> dict:
        compact = [
            {
                "analyst": r.get("analyst"),
                "view": r.get("view"),
                "confidence": r.get("confidence"),
                "summary": r.get("summary"),
                "key_points": r.get("key_points"),
            }
            for r in analyst_results
        ]
        user_content = f"티커: {ticker}\n\n[애널리스트 분석 결과]\n{json.dumps(compact, ensure_ascii=False, indent=2)}"
        result = ask_llm_json(SYSTEM_PROMPT, user_content)
        result["team"] = self.name
        return result
