"""등록된 서비스들을 하나의 FastMCP 서버로 합성한다.

`services`로 일부만 골라 노출할 수 있다(없으면 ARCSOLVE_SERVICES 환경변수, 그것도 없으면 전체).
개별 모듈만 자신의 서버에 붙이고 싶으면 서비스의 `SERVICE.register(mcp)`를 직접 호출하면 된다.
"""

from __future__ import annotations

from fastmcp import FastMCP

from arcsolve.services import select_services


def build_server(services: list[str] | None = None) -> FastMCP:
    mcp = FastMCP("arcsolve")
    for svc in select_services(services):
        svc.register(mcp)
    return mcp
