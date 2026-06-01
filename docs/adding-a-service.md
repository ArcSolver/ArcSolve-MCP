# 새 서비스 추가하기

서비스 하나 = **폴더 하나**. 공통 프레임워크(`server`/`service`/`http`/`oauth`)는 건드리지 않는다.

## 3단계

### 1. 계약 작성 — `arcsolve/services/<name>/contract.py`
상류 API의 '진실'만. 순수 상수 + pydantic 모델, MCP/네트워크 무의존.
```python
from pydantic import BaseModel, Field

BASE_URL = "https://api.example.com"
SOME_ENDPOINT = "/v1/things"          # 엔드포인트는 상수로

class CreateThing(BaseModel):          # 요청 스키마
    title: str = Field(max_length=100)

class ThingResult(BaseModel):          # 응답 스키마
    ok: bool
```
OAuth를 쓰면 `AUTHORIZE_URL` / `TOKEN_URL` / `SCOPES`도 여기에 둔다.

### 2. 도구 작성 — `arcsolve/services/<name>/tools.py`
`register(mcp)` 안에서 `@mcp.tool`을 정의하고 공통 `http`/`oauth`를 쓴다.
도구 이름은 **서비스 prefix 1단**(`example_create_thing`).
```python
from fastmcp import FastMCP
from arcsolve.http import post_form, UpstreamError
from arcsolve.services.example import contract as c

def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def example_create_thing(title: str) -> str:
        """thing을 하나 만든다."""        # 첫 줄이 카탈로그 설명이 된다
        ...
```

### 3. 선언 — `arcsolve/services/<name>/__init__.py`
```python
from arcsolve.service import Service
from arcsolve.services.example.tools import register  # , make_oauth_client (OAuth면)

SERVICE = Service(
    name="example",
    register=register,
    docs_url="https://docs.example.com/api",   # 출처(provenance) — 필수
    summary="한 줄 설명",
    # make_auth_client=make_oauth_client,       # OAuth 쓰는 서비스만 — auth CLI 자동 연결
)
```
**레지스트리는 건드리지 않는다.** `services/`를 스캔해 `SERVICE`를 자동 발견하므로, 폴더를
떨구는 것만으로 등록된다(병렬 추가 시 충돌 없음).

> HTTP는 공통 코어 동사(`arcsolve.http`의 `post_form`/`get_json`/`post_json`)를 재사용한다.
> 서비스 폴더에 **새 서드파티 의존을 추가하지 않는다**(필요 시 통합 단계에서 `pyproject.toml`에 반영).

### 마무리
- `tests/test_<name>_contract.py` → 계약 모델 검증(네트워크 없이)
- `changelog.d/<name>.md` → 한 줄 변경 요약 (예: `- **example**: 도구 X 추가`)
- 통합 단계(개별 에이전트 아님)에서 `arcsolve-mcp catalog` + `arcsolve-mcp changelog` 실행

## 서비스 README 템플릿 (필수)

문서는 **코드 옆에 둔다**: `arcsolve/services/<name>/README.md`. 별도 `docs/<name>.md`를 만들지
않는다(중복=drift). 모든 서비스가 아래 동일한 골격을 따른다.

```markdown
# <Service>
한 줄 설명.

## 계약 출처 (공식 문서)
- API 레퍼런스: <url>
- 인증/토큰: <url>
> 계약 본체는 contract.py 에 코드로 박제되어 있다.

## 엔드포인트
| 종류 | METHOD · PATH |
|------|------|
| ... | ... |
Base: `...` · 인증: `...` · 스코프: `...`

## 셋업
1. 키 발급
2. 인증: `arcsolve-mcp auth <name>`

## 도구
| 도구 | 설명 |
|------|------|
| `<name>_...` | ... |

## 범위 / 제약
- ...

## 확장 포인트
- ...
```

## 어디에 무엇을 쓰나 (요약)

| 문서 | 위치 | 출처(누가 진실인가) |
|------|------|------|
| 계약 레퍼런스(필드·제약) | `contract.py` | **코드** — prose로 중복 금지 |
| 서비스 운영 가이드 | `services/<name>/README.md` | 서비스당 1개 |
| 횡단(아키텍처·이 문서) | `docs/` | 서비스 수와 무관하게 고정 |
| 서비스 카탈로그 | `docs/services.md` | **자동 생성** (`arcsolve-mcp catalog`) |
| 체인지로그 | `changelog.d/<name>.md` → `CHANGELOG.md` | 조각으로 쓰고 **합본** (`arcsolve-mcp changelog`) |
| 공통 작업 규칙 | `AGENTS.md` | 모든 에이전트의 단일 출처 |
