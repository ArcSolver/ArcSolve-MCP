"""등록된 서비스들을 하나의 FastMCP 서버로 합성한다.

`services`로 일부만 골라 노출할 수 있다(없으면 ARCSOLVE_SERVICES 환경변수, 그것도 없으면 전체).
개별 모듈만 자신의 서버에 붙이고 싶으면 서비스의 `SERVICE.register(mcp)`를 직접 호출하면 된다.
"""

from __future__ import annotations

from fastmcp import FastMCP

from arcsolve.services import select_services


def build_server(services: list[str] | None = None) -> FastMCP:
    # mask_error_details=True: 도구에서 처리되지 않은 예외의 원문 str을 클라이언트에 그대로
    # 전송하지 않는다(내부 경로·상류 원문 등 정보 노출 방지). 도구가 의도적으로 반환하는
    # 사람용 메시지(_explain 등)는 영향받지 않는다.
    mcp = FastMCP("arcsolve", mask_error_details=True)
    for svc in select_services(services):
        svc.register(mcp)
    return mcp
