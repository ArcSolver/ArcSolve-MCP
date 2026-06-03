# AGENTS.md

> [English](AGENTS.md) · **한국어**

<!-- i18n-source: AGENTS.md -->

이 저장소에서 작업하는 **모든 에이전트(사람·AI)**가 따르는 단일 규칙. 생판 모르고 들어와도
이 문서 + **정답 예시**(MCP 서비스 = `kakao` / Skill = `academic-discovery`)만 보면
새 서비스나 스킬을 정확히 구현할 수 있어야 한다.

## 미션

인기 서비스의 **공식 API 계약으로 검증된 능력**을 두 포맷으로 묶는 오픈소스 모음.

- **MCP 서비스** — 하나의 FastMCP 서버가 여러 서비스를 합성해 *런타임 도구*로 노출.
- **Skill** — Claude에게 *그 도구·워크플로를 어떻게 쓰는지* 가르치는 파일 아티팩트.

둘은 경쟁이 아니라 **같은 계약 백본 위의 두 배포 포맷**이다. 설계 배경은
[docs/architecture.md](docs/architecture.ko.md).

## 두 산출물 포맷

| | MCP 서비스 | Skill |
|---|---|---|
| 무엇 | 런타임에 *도구가 무엇인지* 노출 | 에이전트에게 *어떻게 쓰는지* 가르침 |
| 단위 | `arcsolve/services/<name>/` 폴더 하나 | `skills/<name>/` 폴더 하나 |
| 배포 | FastMCP 서버(stdio/HTTP)로 serve | `~/.claude/skills/`에 설치, 컨텍스트에 점진 로드 |
| 계약 | API 요청/응답 pydantic 모델 (`contract.py`) | `SKILL.md` frontmatter(공개 약속) + 본문 지시의 출처 |

**상보성:** 한 도메인이 두 포맷을 함께 낼 수 있다 — `kakao` MCP 도구 + "카카오 메시징을 잘 쓰는 법"
스킬. 재사용은 **도구 경계**에서 일어난다: 스킬은 `contract.py`를 import하지 않고 **실행 중인 ArcSolve
MCP 서버의 도구를 오케스트레이션**한다(규칙 2-2). 검증된 계약은 MCP 쪽 단일 출처로 남는다.

## 황금 규칙: 정답 예시를 복제하라

- **MCP 서비스**는 `arcsolve/services/kakao/`가 정답이다.
- **Skill**은 `skills/academic-discovery/`가 정답이다 — 여러 학술 출처(arXiv·Crossref·OpenAlex·
  PubMed·Semantic Scholar)를 가로질러 논문을 탐색·교차검증하는 **다중 서비스 오케스트레이션**.
  *(미니멀 단일 서비스 예시는 후속 — 후보: `skills/wikipedia-lookup/`.)*

산문 규칙이 헷갈리면 정답 예시 코드가 최종 기준이다.

## 입력과 산출물

**입력**: [docs/providers.md](docs/providers.md)에서 네가 맡은 대상 블록(공식 문서 링크·스코프·계획).
각 블록은 `format: mcp | skill | both`로 어떤 포맷이 목표인지 명시한다.

### MCP 서비스를 맡았다면

산출물: `arcsolve/services/<name>/` 폴더 하나 + changelog 조각 + 테스트 **2종**(계약·도구).
**그 밖은 건드리지 않는다.**

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

### Skill을 맡았다면

산출물: `skills/<name>/` 폴더 하나 + changelog 조각 + 테스트 1종(스킬).
**그 밖은 건드리지 않는다.**

```
skills/<name>/
├── SKILL.md        # 계약: frontmatter(name·description·allowed-tools) + 워크플로 지시 본문
├── scripts/        # (선택) 순수 헬퍼만 — stdlib 전용, 상류 API는 직접 치지 않음(MCP 도구가 담당)
├── references/     # (선택) 점진 로드용 레퍼런스 문서
└── README.md       # 고정 템플릿 + "계약 출처" + "필요 MCP 도구" 섹션 (docs/adding-a-skill.md)
tests/test_<name>_skill.py       # 정적 불변식: frontmatter·참조 해소·allowed-tools가 실재 도구명과 일치, 네트워크 없음
evals/<name>/                    # 품질 게이트: eval(skill-creator 하니스) — 위치/형식은 docs/adding-a-skill.md
changelog.d/skill-<name>.md      # 한 줄 변경 요약 (서비스와 이름 충돌 방지로 'skill-' prefix)
```

`SKILL.md` frontmatter는 다음을 따른다:
- `name`: 폴더명과 동일, 소문자·하이픈.
- `description`: **3인칭으로 "무엇을 + 언제(트리거)"**를 정확히. 과대선언 금지(이게 공개 약속 = 계약이다).
- `allowed-tools`: 오케스트레이션할 **ArcSolve MCP 도구명**을 명시(예: `kakao_send_text_to_me`). 정적 테스트가 실재 도구와 대조한다.

## 규칙

### 1. 계약 충실도 (가장 중요 — 두 포맷 공통)
- **모든 사실(엔드포인트·필드·명령·API 동작)은 공식 문서 링크에서 실재해야 한다.** 학습지식으로 채우지 말 것.
- **문서가 모호하면 지어내지 말고** `# TODO(provenance): <무엇이 불확실한지>`를 남기고 보고한다.
- 계약 출처 링크는 `README.md`의 "계약 출처" 섹션에 명시한다(provenance 테스트가 검사).
- **MCP 서비스:** `contract.py`의 모든 엔드포인트·필드에 **출처 주석/링크**. 모델은 pydantic, 길이·필수·열거 제약을 문서대로.
- **Skill:** `description`은 실제 동작과 일치(과대선언 금지). 본문의 **사실 부분**(명령·도구명·파라미터)만 출처 추적 대상이다. **워크플로/판단**은 외부 출처가 없으므로 provenance가 아니라 **eval**로 품질을 검증한다(규칙 6).

### 2. 공통 코어 재사용 (재발명 금지 — MCP 서비스)
- HTTP: `arcsolve.http`의 `post_form` / `get_json` / `post_json`(+ `bearer(token)` 헤더 헬퍼).
  직접 httpx 세션을 만들지 말 것. 코어에 없는 호출 형태가 필요하면 코어를 늘려라(서비스 폴더 안에서 X).
- OAuth: `arcsolve.oauth.OAuthClient`(authcode+PKCE+refresh+토큰저장). OAuth 쓰는 서비스는
  `__init__.py`에서 `SERVICE`에 `make_auth_client`를 넘기면 `arcsolve-mcp auth <name>`이 코어 수정 없이 동작.

### 2-1. 의존성 (병렬 충돌 방지)
- 서비스 폴더는 **표준 라이브러리 + 공통 코어만**, 스킬 스크립트는 **표준 라이브러리만** 쓴다(스킬은 `arcsolve`를 import하지 않는다 — 규칙 2-2). 새 서드파티 의존을 폴더에서 추가하지 말 것.
- 무거운 SDK가 꼭 필요하면 PR 설명에 명시 → **통합 단계에서** `pyproject.toml`/`uv.lock`에 반영(필요 시 extras로 격리).

### 2-2. 재사용은 도구 경계에서 (Skill — ArcSolve의 핵심)
- 스킬은 `contract.py`를 **import하지 않는다.** 검증된 계약은 MCP 서비스에 단일 출처로 남고,
  스킬은 **실행 중인 ArcSolve MCP 서버의 도구를 오케스트레이션**한다(스킬 = 도구를 잘 엮는 지시 + 얇은 글루).
- 어떤 MCP 서비스/도구에 의존하는지 frontmatter `allowed-tools`와 README "필요 MCP 도구"에 명시 → 카탈로그가 표시.
- API 호출은 **MCP 도구가 담당**한다. 스킬 스크립트가 상류 API를 직접 치지 않는다(그건 서비스의 일).

### 3. 네이밍·노출
- **MCP 도구 이름**은 서비스 1단 prefix: `<name>_<action>` (예: `kakao_send_text_to_me`).
- `SERVICE`는 `arcsolve/services/<name>/__init__.py`에 선언만 하면 **레지스트리가 자동 발견**한다.
- **Skill 이름**은 폴더명 = frontmatter `name`. 도구 prefix와는 별개 네임스페이스(페어 스킬은 도메인명을 의도적으로 공유해도 됨).
- 레지스트리/카탈로그 파일을 편집하지 않는다(자동 발견·자동 생성).

### 4. "두 개의 OAuth" 혼동 금지 (MCP 서비스)
- 상류 OAuth(서버→상류 API, 예: 카카오 로그인)는 `oauth.py`로 처리. MCP transport OAuth(스펙)는 별개이며
  로컬 stdio에선 불필요. 자세히는 [docs/architecture.md](docs/architecture.ko.md).

### 5. 격리 — 절대 건드리지 말 것 (병렬 충돌 방지)
- `arcsolve/services/__init__.py` (서비스 레지스트리 — 자동 발견)
- `skills/__init__.py` (스킬 레지스트리 — 자동 발견)
- `docs/services.md`, `docs/skills.md` (카탈로그 — 자동 생성)
- `CHANGELOG.md` (본체 — 조각에서 합본)
- `pyproject.toml` / `uv.lock` (의존성 — 통합 단계 전담)
- 다른 서비스·스킬의 폴더
- 공통 코어(`server/service/skill/http/oauth/catalog/changelog`)는 정당한 이유 없이 수정 금지
  (단, 코어 HTTP 동사 확충처럼 모두에게 이로운 변경은 별도 PR로 허용)

### 6. 품질 게이트 (Skill — 결정적 테스트 + eval)
- `test_<name>_skill.py`는 **정적 불변식만** 검증한다(frontmatter 필수 필드·참조 해소·`allowed-tools`가 실재 도구명과 일치). 네트워크·모델 없음.
- 스킬의 실제 품질("Claude를 옳게 행동시키는가")은 **eval**로 검증한다(skill-creator 하니스). 서비스의 결정적 단위테스트와 **다른 종류의 보증**임을 인지한다.

## Definition of Done

### MCP 서비스
- [ ] `contract.py`: 엔드포인트=상수, pydantic 모델, **필드마다 출처**, 문서 제약 반영
- [ ] `tools.py`: `register(mcp)` + `@mcp.tool`, prefix 1단, 공통 `http`/`oauth` 사용, 에러 매핑
- [ ] `__init__.py`: `SERVICE = Service(name, register, docs_url, summary, make_auth_client?)` — **`docs_url` 필수**, OAuth면 `make_auth_client` 지정
- [ ] `README.md`: 템플릿 + "계약 출처" 공식 문서 링크(provenance 테스트가 검사)
- [ ] `tests/test_<name>_contract.py`: 계약 모델 검증, 네트워크 없이 통과
- [ ] `tests/test_<name>_tools.py`: 도구 런타임 검증 — `conftest.py`의 FakeMCP/RecordingHTTP 사용, 네트워크 없이 통과
- [ ] `changelog.d/<name>.md`: 변경 요약
- [ ] 서비스 폴더에 새 서드파티 의존 추가 안 함
- [ ] `uv run pytest -q` 통과 · `uv run ruff check .` 통과
- [ ] 환각 없음: 미확정 사항은 `TODO(provenance)`로 표시

### Skill
- [ ] `SKILL.md`: frontmatter `name`(폴더명 일치) + `description`(3인칭, "무엇을+언제", 과대선언 금지) + `allowed-tools`(오케스트레이션할 MCP 도구명) + 워크플로 지시 본문
- [ ] 본문의 **사실 부분**(명령·도구명·파라미터)에 출처, 미확정은 `TODO(provenance)`
- [ ] `contract.py`를 import하지 않음 · 스크립트가 있으면 stdlib 전용 순수 헬퍼(상류 API 직접 호출 X)
- [ ] `README.md`: 템플릿 + "계약 출처" + "필요 MCP 도구" 섹션(provenance 테스트가 검사)
- [ ] `tests/test_<name>_skill.py`: 정적 불변식(frontmatter·참조 해소·`allowed-tools`가 실재 도구명과 일치), 네트워크 없이 통과
- [ ] **eval 통과**: skill-creator 하니스로 품질 검증(규칙 6)
- [ ] `changelog.d/skill-<name>.md`: 변경 요약
- [ ] `uv run pytest -q` 통과 · `uv run ruff check .` 통과

## 명령

```bash
uv run pytest -q              # 테스트
uv run ruff check .           # 린트
# (통합 단계 전담 — 개별 에이전트는 실행 안 함)
uv run arcsolve-mcp catalog   # docs/services.md + docs/skills.md 재생성
uv run arcsolve-mcp changelog # CHANGELOG.md 합본
```

새 서비스 추가는 [docs/adding-a-service.md](docs/adding-a-service.ko.md),
새 스킬 추가는 [docs/adding-a-skill.md](docs/adding-a-skill.ko.md) 참고.
