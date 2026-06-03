from arcsolve.service import Service
from arcsolve.services.airkorea.tools import register

SERVICE = Service(
    name="airkorea",
    register=register,
    docs_url="https://www.data.go.kr/data/15073861/openapi.do",
    summary="에어코리아 대기오염정보 읽기(시도·측정소 실시간 측정 + 예보)",
    # 서비스키는 쿼리 파라미터 serviceKey(사전발급) — 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
