from arcsolve.service import Service
from arcsolve.services.ev_charger.tools import register

SERVICE = Service(
    name="ev_charger",
    register=register,
    docs_url="https://www.data.go.kr/data/15076352/openapi.do",
    summary="전기차 충전소(한국환경공단) 정보·실시간 상태 읽기(충전소 정보 + 충전기 실시간 상태)",
    # 서비스키는 쿼리 파라미터 serviceKey(사전발급) — 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
