from arcsolve.service import Service
from arcsolve.services.arxiv.tools import register

SERVICE = Service(
    name="arxiv",
    register=register,
    docs_url="https://info.arxiv.org/help/api/user-manual.html",
    summary="arXiv 학술 프리프린트 읽기(검색·id 조회, Atom XML)",
    # 무인증(키 없음). 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
