# AGENTS.md

이 저장소에서 작업하는 **모든 에이전트(사람·AI)**가 따르는 단일 규칙. 생판 모르고 들어와도
이 문서 + `kakao` 예시만 보면 새 서비스를 정확히 구현할 수 있어야 한다.

## 미션

인기 서비스의 **공개 API를 MCP 도구로 묶는** 오픈소스 모음. 하나의 FastMCP 서버가 여러 서비스를
합성해 노출하고, **서비스 하나 = 폴더 하나**다. 설계 배경은 [docs/architecture.md](docs/architecture.md).

## 황금 규칙: kakao를 복제하라

`arcsolve/services/kakao/`가 **정답 예시(spec by example)**다. 새 서비스는 이 모양을 그대로 따른다.
산문 규칙이 헷갈리면 kakao 코드가 최종 기준이다.

## 입력과 산출물

- **입력**: [docs/providers.md](docs/providers.md)에서 네가 맡은 서비스의 블록(공식 문서 링크·스코프·계획 도구).
- **산출물**: `arcsolve/services/<name>/` 폴더 하나 + 네 changelog 조각 + 네 테스트 **2종**(계약·도구). **그 밖은 건드리지 않는다.**

```
arcsolve/services/<name>/
├── contract.py     # 계약: 엔드포인트 상수 + pydantic 요청/응답 모델 (MCP/네트워크 무의존)
├── tools.py        # MCP 도구: register(mcp)에서 @mcp.tool, 공통 http/oauth 재사용
├── __init__.py     # SERVICE = Service(...)  ← 자동 발견됨
└── README.md       # 고정 템플릿 (docs/adding-a-service.md)
tests/test_<name>_contract.py    # 계약 모델 검증 (네트워크 없음)
tests/test_<name>_tools.py       # 도구 런타임 검증 (요청 조립·응답 파싱·에러 매핑)
                                 #   — tests/conftest.py의 FakeMCP/RecordingHTTP 픽스처 사용, 네트워크 없음
changelog.d/<name>.md            # 한 줄 변경 요약
```

## 규칙

### 1. 계약 충실도 (가장 중요)
- `contract.py`의 **모든 엔드포인트·필드는 공식 문서 링크에서 실재해야 한다.** 학습지식으로 채우지 말 것.
- 각 계약 요소에 **출처 주석/링크**를 남긴다. 모델은 pydantic, 길이·필수·열거 제약을 문서대로 반영.
- **문서가 모호하면 지어내지 말고** `# TODO(provenance): <무엇이 불확실한지>`를 남기고 보고한다.
- 계약 출처 링크는 `README.md`의 "계약 출처" 섹션에도 명시한다.

### 2. 공통 코어 재사용 (재발명 금지)
- HTTP: `arcsolve.http`의 `post_form` / `get_json` / `post_json`(+ `bearer(token)` 헤더 헬퍼).
  직접 httpx 세션을 만들지 말 것. 코어에 없는 호출 형태가 필요하면 코어를 늘려라(서비스 폴더 안에서 X).
- OAuth: `arcsolve.oauth.OAuthClient`(authcode+PKCE+refresh+토큰저장). OAuth 쓰는 서비스는
  `__init__.py`에서 `SERVICE`에 `make_auth_client`를 넘기면 `arcsolve-mcp auth <name>`이 코어 수정 없이 동작.

### 2-1. 의존성 (병렬 충돌 방지)
- 서비스 폴더는 **표준 라이브러리 + 공통 코어만** 사용한다. 새 서드파티 의존을 서비스 폴더에서 추가하지 말 것.
- 무거운 SDK가 꼭 필요하면 PR 설명에 명시 → **통합 단계에서** `pyproject.toml`/`uv.lock`에 반영(필요 시 extras로 격리).

### 3. 네이밍·노출
- 도구 이름은 **서비스 1단 prefix**: `<name>_<action>` (예: `kakao_send_text_to_me`).
- `SERVICE`는 `__init__.py`에 선언만 하면 **레지스트리가 자동 발견**한다. 레지스트리 파일을 편집하지 않는다.

### 4. "두 개의 OAuth" 혼동 금지
- 상류 OAuth(서버→상류 API, 예: 카카오 로그인)는 `oauth.py`로 처리. MCP transport OAuth(스펙)는 별개이며
  로컬 stdio에선 불필요. 자세히는 [docs/architecture.md](docs/architecture.md).

### 5. 격리 — 절대 건드리지 말 것 (병렬 충돌 방지)
- `arcsolve/services/__init__.py` (레지스트리 — 자동 발견)
- `docs/services.md` (카탈로그 — 자동 생성)
- `CHANGELOG.md` (본체 — 조각에서 합본)
- `pyproject.toml` / `uv.lock` (의존성 — 통합 단계 전담)
- 다른 서비스의 폴더
- 공통 코어(`server/service/http/oauth/catalog/changelog`)는 정당한 이유 없이 수정 금지
  (단, 코어 HTTP 동사 확충처럼 모두에게 이로운 변경은 별도 PR로 허용)

## Definition of Done

- [ ] `contract.py`: 엔드포인트=상수, pydantic 모델, **필드마다 출처**, 문서 제약 반영
- [ ] `tools.py`: `register(mcp)` + `@mcp.tool`, prefix 1단, 공통 `http`/`oauth` 사용, 에러 매핑
- [ ] `__init__.py`: `SERVICE = Service(name, register, docs_url, summary, make_auth_client?)` — **`docs_url` 필수**(빈값 금지), OAuth면 `make_auth_client` 지정
- [ ] `README.md`: 템플릿 + "계약 출처" 공식 문서 링크(provenance 테스트가 검사)
- [ ] `tests/test_<name>_contract.py`: 계약 모델 검증, 네트워크 없이 통과
- [ ] `tests/test_<name>_tools.py`: 도구 런타임 검증(요청 조립·응답 파싱·에러 매핑·자격증명 누락) — `conftest.py`의 FakeMCP/RecordingHTTP 사용, 네트워크 없이 통과
- [ ] `changelog.d/<name>.md`: 변경 요약
- [ ] 서비스 폴더에 새 서드파티 의존 추가 안 함
- [ ] `uv run pytest -q` 통과 · `uv run ruff check .` 통과
- [ ] 환각 없음: 미확정 사항은 `TODO(provenance)`로 표시

## 명령

```bash
uv run pytest -q              # 테스트
uv run ruff check .           # 린트
# (통합 단계 전담 — 개별 에이전트는 실행 안 함)
uv run arcsolve-mcp catalog   # docs/services.md 재생성
uv run arcsolve-mcp changelog # CHANGELOG.md 합본
```

새 서비스 추가 절차는 [docs/adding-a-service.md](docs/adding-a-service.md) 참고.
