from arcsolve.service import Service
from arcsolve.services.egen.tools import register

SERVICE = Service(
    name="egen",
    register=register,
    docs_url="https://www.data.go.kr/data/15000563/openapi.do",
    summary="E-Gen 응급의료정보 읽기(응급실 실시간 가용병상·중증질환 수용가능·응급의료기관 목록)",
    # 서비스키는 쿼리 파라미터 serviceKey(사전발급) — 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
