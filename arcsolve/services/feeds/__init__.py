from arcsolve.service import Service
from arcsolve.services.feeds.tools import register

SERVICE = Service(
    name="feeds",
    register=register,
    docs_url="https://www.rssboard.org/rss-specification",
    summary="RSS/Atom/RDF 피드 읽기(임의 피드 URL → 메타·최근 항목)",
    # 무인증(키 없음). 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
