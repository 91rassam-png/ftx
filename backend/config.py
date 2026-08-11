"""
설정 모듈: .env 파일에서 API 키를 로드합니다.
"""
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# 리서치에 참고할 커뮤니티 소스 (미국 티커용, 인증 불필요한 공개 JSON 엔드포인트)
REDDIT_SUBREDDITS = ["stocks", "wallstreetbets", "investing"]

if not GEMINI_API_KEY:
    print("[경고] GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
