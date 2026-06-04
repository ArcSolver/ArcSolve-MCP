"""ArcSolve MCP 엔트리포인트.

  arcsolve                  # 전체(또는 ARCSOLVE_SERVICES) 서비스로 서버 실행 (stdio)
  arcsolve serve kakao      # 지정한 서비스만 노출
  arcsolve list             # 사용 가능한 서비스 목록
  arcsolve skills           # 사용 가능한 스킬 목록
  arcsolve auth kakao       # 카카오 최초 1회 인증 → refresh_token 저장
  arcsolve catalog          # docs/services.md + docs/skills.md 재생성 (자동)
  arcsolve changelog        # changelog.d/ 조각 → CHANGELOG.md 합본
"""

from __future__ import annotations

import asyncio
import sys
import urllib.parse
import webbrowser

from arcsolve.server import build_server


def _parse_redirect(raw: str) -> tuple[str, str | None]:
    """사용자가 붙여넣은 값에서 (code, state)를 뽑는다.

    'code='가 들어 있으면 redirect URL(또는 쿼리스트링)로 보고 파싱하고, 아니면 입력 전체를
    code로 취급한다(state 없음). state가 있으면 exchange_code가 CSRF 대조에 쓴다.
    """
    if "code=" not in raw:
        return raw, None
    qs = urllib.parse.urlparse(raw).query or raw
    params = urllib.parse.parse_qs(qs)
    code = (params.get("code") or [raw])[0]
    state = (params.get("state") or [None])[0]
    return code, state


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
    print("리다이렉트된 주소(redirect_uri) 전체를 그대로 붙여넣으세요(또는 ?code=... 값만).\n")
    print(url + "\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    raw = input("redirect URL 전체(또는 code) = ").strip()
    code, state = _parse_redirect(raw)
    tok = asyncio.run(client.exchange_code(code, state=state))
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
