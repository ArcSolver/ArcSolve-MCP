"""ArcSolve MCP 엔트리포인트.

  arcsolve-mcp                  # 전체(또는 ARCSOLVE_SERVICES) 서비스로 서버 실행 (stdio)
  arcsolve-mcp serve kakao      # 지정한 서비스만 노출
  arcsolve-mcp list             # 사용 가능한 서비스 목록
  arcsolve-mcp skills           # 사용 가능한 스킬 목록
  arcsolve-mcp auth kakao       # 카카오 최초 1회 인증 → refresh_token 저장
  arcsolve-mcp catalog          # docs/services.md + docs/skills.md 재생성 (자동)
  arcsolve-mcp changelog        # changelog.d/ 조각 → CHANGELOG.md 합본
"""

from __future__ import annotations

import asyncio
import sys
import webbrowser

from arcsolve.server import build_server


def _auth(name: str) -> None:
    from arcsolve.services import available, load_service

    svc = load_service(name)
    if svc is None:
        raise SystemExit(f"알 수 없는 서비스: {name} (사용 가능: {', '.join(available())})")
    if svc.make_auth_client is None:
        raise SystemExit(f"'{name}'는 별도 인증이 필요 없습니다.")

    client = svc.make_auth_client()
    if not client.client_id:
        raise SystemExit(f"먼저 {name.upper()} 자격증명(예: REST API 키)을 환경변수로 설정하세요.")

    url = client.authorize_url_for_login()
    print("브라우저에서 아래 URL을 열어 로그인/동의한 뒤,")
    print("리다이렉트된 주소(redirect_uri)의 ?code=... 값을 복사해 붙여넣으세요.\n")
    print(url + "\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    code = input("code = ").strip()
    tok = asyncio.run(client.exchange_code(code))
    print("\n✅ 인증 완료. ~/.arcsolve/credentials.json 에 저장했습니다(권한 0600).")
    print("호스트 설정의 env에 refresh_token을 직접 넣어도 됩니다(평문 노출 주의):")
    print(f"  {name.upper()}_REFRESH_TOKEN={tok.get('refresh_token')}")


def _catalog() -> None:
    from arcsolve.catalog import write_catalog, write_skills_catalog

    spath = asyncio.run(write_catalog())
    kpath = write_skills_catalog()
    print(f"카탈로그 생성: {spath} · {kpath}")


def _changelog() -> None:
    from arcsolve.changelog import compile_changelog

    path = compile_changelog()
    print(f"체인지로그 합본: {path}")


def _serve(names: list[str]) -> None:
    try:
        server = build_server(names or None)
    except ValueError as e:
        raise SystemExit(str(e))
    server.run()


def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "serve"
    if cmd == "auth":
        _auth(argv[1] if len(argv) > 1 else "kakao")
    elif cmd == "catalog":
        _catalog()
    elif cmd == "changelog":
        _changelog()
    elif cmd == "list":
        from arcsolve.services import available

        print("사용 가능한 서비스:", ", ".join(available()))
    elif cmd == "skills":
        from arcsolve.skill import available as skills_available

        names = skills_available()
        print("사용 가능한 스킬:", ", ".join(names) if names else "(없음)")
    elif cmd == "serve":
        _serve(argv[1:])
    else:
        raise SystemExit(
            f"알 수 없는 명령: {cmd} (serve | list | skills | auth | catalog | changelog)"
        )


if __name__ == "__main__":
    main()
