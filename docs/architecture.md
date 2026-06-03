# 아키텍처

ArcSolve MCP는 **인기 서비스의 공개 API를 MCP 도구로 묶는** 모음이다.
하나의 FastMCP 서버가 여러 서비스를 합성해 노출하고, 각 서비스는 **폴더 하나**로 끝난다.

## 3개 층

```
호스트(server.py)        여러 서비스를 합성한 단일 FastMCP. transport(stdio/HTTP) 담당.
   └─ 서비스(services/<name>)   register(mcp)로 도구를 붙이는 단위. 서비스=폴더 하나.
        ├─ contract.py     상류 API의 '진실'(엔드포인트·스코프·요청/응답 모델). MCP 무의존.
        └─ tools.py        계약을 호출하는 얇은 MCP 도구.
공통(http.py / oauth.py)  모든 서비스가 공유하는 HTTP 호출 + OAuth.
```

## 핵심 원칙: 계약과 도구의 분리

- **`contract.py` = "API가 무엇인가".** 순수 상수 + pydantic 모델. 네트워크/MCP를 모른다.
  이 파일이 곧 "공식 계약 기반 자체 클라이언트"라는 증거이자 라이선스 클린의 근거다.
- **`tools.py` = "그걸 어떻게 도구로 노출하나".** `register(mcp)` 안에서 `@mcp.tool`을 정의하고,
  `도구 인자 → 계약 모델 → 공통 HTTP → 계약 응답 → 도구 결과`로 잇는 얇은 층.

이 분리 덕분에 서비스는 명확히 구분되면서도 구조가 균일하고, 계약 변경 지점이 한 파일에 모인다.

## 단일 합성 호스트

`server.py`는 레지스트리(`services/__init__.py`)가 자동 발견한 서비스를 순회하며 각 서비스의
`register(mcp)`를 호출해 **하나의 서버**에 도구를 붙인다. 사용자는 명령 하나만 실행하고,
원하는 서비스만 골라 노출한다. 각 서비스는 단독 테스트도 가능하다.

도구 이름은 **서비스 1단 prefix**만 쓴다(`kakao_send_text_to_me`). 모델에 노출되는 이름이
짧을수록 좋기 때문에 `arcsolve.kakao.*`처럼 다단계로 가지 않는다.

### 원하는 모듈만 노출

`build_server(services)` 또는 `select_services()`가 노출 대상을 고른다
(우선순위: 인자 > `ARCSOLVE_SERVICES` 환경변수 > 전체). CLI는 `arcsolve-mcp serve kakao`.
개별 모듈만 남의 서버에 붙이려면 `SERVICE.register(mcp)`를 직접 호출한다.

레지스트리는 **지연·격리 로딩**이다:
- `available()`은 import 없이 폴더만 스캔한다 → 한 서비스가 깨져도 목록은 멀쩡.
- `select_services(names)`는 **선택된 것만 import**한다 → 개별 사용 시 나머지 서비스/의존성을 안 불러옴.
- import는 서비스별 `try/except`로 격리 → 미완성/오류 서비스 하나가 전체(테스트·카탈로그·서버)를 죽이지 않음.

> **의존성 규칙:** 서비스 폴더는 표준 라이브러리 + 공통 코어만 쓴다. 무거운 SDK가 필요하면
> `pyproject.toml`의 optional extras(`arcsolve-mcp[heavy]`)로 격리하고, **의존성 추가는 통합
> 단계에서** 반영한다(서비스 에이전트가 `pyproject.toml`/`uv.lock`을 병렬 편집하면 충돌하므로).

## "두 개의 OAuth"를 혼동하지 말 것

| | 무엇 | 어디 |
|---|---|---|
| **상류 OAuth** | 서버가 *유저 대신 상류 API에* 인증 (예: 카카오 로그인 → `talk_message`) | `oauth.py` + 서비스 `contract.py` |
| **MCP transport OAuth** | MCP 클라이언트↔서버 인증 (스펙의 OAuth 2.1, **HTTP transport일 때만**) | 로컬 stdio에선 **불필요** |

MVP는 로컬 stdio + 상류 OAuth만 쓴다. 원격 배포로 갈 때만 transport 인증을 추가한다.

## MCP 스펙 대응

- 프로토콜은 **직접 구현하지 않는다.** FastMCP에 올라타 스펙 추적을 위임한다
  (현재 stable `2025-11-25`, 다음 RC `2026-07-28`의 stateless core 전환도 SDK가 흡수).
- Transport는 **stdio(기본) + Streamable HTTP** 두 가지로 고정. 새 transport를 만들지 않는다.
- 장기 실행 작업(Tasks)·서버 렌더 UI(MCP Apps)는 현재 미사용. 대부분의 공개 API 호출이
  동기 req/res라서다. `얇은 도구 → 계약 호출` 구조라 나중에 Task로 감싸기 쉽다.

## 스킬 — 두 번째 배포 포맷

MCP 서비스가 *런타임에 도구가 무엇인지* 노출한다면, **스킬**은 *그 도구를 어떻게 쓰는지*를 Claude에게
가르치는 파일 아티팩트다(`skills/<name>/SKILL.md`). 서버가 아니라 `~/.claude/skills/`에 설치되어
컨텍스트에 점진 로드된다.

- **재사용은 도구 경계에서.** 스킬은 `contract.py`를 import하지 않고 실행 중인 ArcSolve MCP 도구를
  오케스트레이션한다. 검증된 계약은 MCP 쪽 단일 출처로 남고, 스킬은 그 위의 워크플로다.
- **자동 발견.** `arcsolve/skill.py`가 레포 루트 `skills/`를 스캔해 `SKILL.md` frontmatter에서 `Skill`을
  만든다(서비스 레지스트리와 같은 데이터-스캔 철학, import 없음).
- **검증.** 정적 테스트는 frontmatter·`allowed-tools`↔실재 도구명 일치 같은 구조 불변식만 본다.
  실제 품질은 eval로 검증한다(서비스의 결정적 단위테스트와 **다른 종류의 보증**).

자세한 절차는 [adding-a-skill.md](adding-a-skill.md).

## 파일 지도

| 경로 | 역할 |
|------|------|
| `arcsolve/server.py` | 서비스 합성 → 단일 FastMCP |
| `arcsolve/service.py` | `Service` = 모든 서비스의 균일 계약 |
| `arcsolve/http.py` | 공유 HTTP 호출 + `UpstreamError` |
| `arcsolve/oauth.py` | 범용 OAuth2(authcode+refresh) + 토큰 저장소 |
| `arcsolve/catalog.py` | 레지스트리 → `docs/services.md` + `docs/skills.md` 자동 생성 |
| `arcsolve/skill.py` | `Skill` = 스킬의 균일 계약 + `skills/` 자동 발견(`SKILL.md` frontmatter) |
| `arcsolve/services/<name>/` | 서비스 하나 = `contract.py` + `tools.py` + `README.md` |
| `skills/<name>/` | 스킬 하나 = `SKILL.md`(+ `scripts/`·`references/`) + `README.md` |

문서 배치 규칙은 [adding-a-service.md](adding-a-service.md) 참고.
