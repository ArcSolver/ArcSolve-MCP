from arcsolve.service import Service
from arcsolve.services.tago_transit.tools import register

SERVICE = Service(
    name="tago_transit",
    register=register,
    docs_url="https://www.data.go.kr/data/15098530/openapi.do",
    summary="TAGO 전국 대중교통 통합 읽기(버스 도착·정류소·노선 + 고속/시외버스 + 열차)",
    # 서비스키는 쿼리 파라미터 serviceKey(사전발급, **Decoding 키**) — 인터랙티브 OAuth 아님
    # → make_auth_client 없음. 단일 키로 TAGO 네임스페이스 1613000의 6개 서비스 전부 커버.
)
