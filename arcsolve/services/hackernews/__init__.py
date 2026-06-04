from arcsolve.service import Service
from arcsolve.services.hackernews.tools import register

SERVICE = Service(
    name="hackernews",
    register=register,
    docs_url="https://github.com/HackerNews/API",
    summary="Hacker News 읽기(아이템·랭킹·검색·사용자 — Firebase + Algolia)",
    # 무인증(키 없음). 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
