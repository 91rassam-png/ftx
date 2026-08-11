"""
Gemini API 호출을 담당하는 얇은 래퍼 (google-genai SDK 사용).
각 에이전트는 이 모듈을 통해 시스템 프롬프트 + 데이터를 넘기고 분석 텍스트를 받는다.

주의: Gemini 3.x 계열부터 temperature/top_p/top_k 파라미터가 deprecated 되어
무시되며, 향후에는 아예 에러를 반환할 예정이라 여기서는 사용하지 않는다.
출력 형식을 안정적으로 통제하려면 system_instruction에 명확한 규칙을 적는다.
"""
import json
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def ask_llm(system_prompt: str, user_content: str, max_tokens: int = 1200) -> str:
    """시스템 프롬프트와 유저 컨텐츠를 넘겨 Gemini의 텍스트 응답을 받는다."""
    if _client is None:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다. .env를 확인하세요.")

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        ),
    )
    return (response.text or "").strip()


def ask_llm_json(system_prompt: str, user_content: str, max_tokens: int = 1200) -> dict:
    """JSON 형식 응답을 강제하고 파싱까지 해서 dict로 반환한다.
    Gemini의 response_mime_type=application/json 모드를 사용해 형식을 강제한다."""
    if _client is None:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다. .env를 확인하세요.")

    strict_system = (
        system_prompt
        + "\n\n반드시 순수 JSON 객체 하나만 출력하라. 코드블록(```)이나 설명, 서론은 절대 포함하지 마라."
    )
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=strict_system,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    raw = (response.text or "").strip()
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 파싱 실패 시 원문을 raw_text 필드에 담아 반환 (파이프라인이 죽지 않도록)
        return {"parse_error": True, "raw_text": raw}
