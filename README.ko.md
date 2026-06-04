# ArcSolve-Kit

> [English](README.md) · **한국어**

<!-- i18n-source: README.md -->

[![CI](https://github.com/ArcSolver/ArcSolve-Kit/actions/workflows/ci.yml/badge.svg)](https://github.com/ArcSolver/ArcSolve-Kit/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

> 인기 서비스의 **공식 API 계약으로 검증된 능력**을 두 포맷으로 묶는 오픈소스 모음.

- **MCP 서비스** — 하나의 MCP 서버가 여러 서비스를 합성해 *런타임 도구*로 노출. 서비스 = **폴더 하나 = 계약 + 도구**.
- **Skill** — 그 도구를 *어떻게 잘 쓰는지* Claude에게 가르치는 파일 아티팩트. 스킬 = **폴더 하나 = `SKILL.md`**.

검증된 계약(`contract.py`)은 MCP 쪽 단일 출처로 남고, 스킬은 그 위에서 도구를 오케스트레이션한다.

## 왜 만드나

제품을 만들 때 늘 번거로운 세 가지가 있다. (1) SNS마다 API·인증·메시지 포맷이 달라 채팅/알림(봇)을
붙이기가 매번 힘들고, (2) 조사에 필요한 외부 정보를 가져오는 것도 출처마다 제각각이며, (3) 이 둘을
**한곳에서 일관되게** 묶어 관리하는 도구는 드물다. ArcSolve-Kit은 공개 API **계약**을 균일한 MCP
도구로 노출해 이 마찰을 없앤다.

## 비전

공개된 계약을 MCP화하여 **모델**이 다양한 제품에 손쉽게 접근·소통하게 하고, **에이전틱 워크플로
오픈소스 개발자**가 우리 MCP를 레고처럼 조립해 원하는 서비스를 빠르게 만들게 한다.

## 방향 (로드맵)

1. **다국어 지원** — 도구 설명·문서·메시지를 여러 언어로 제공한다.
2. **더 다양한 서비스** — 메시징·학술·생산성을 넘어 계속 폭을 넓힌다.
3. **일관된 계약 기반 확장** — 모든 서비스가 *폴더 하나 = 계약 + 도구*라는 **동일 구조**를 따른다.
   이 균일함은 **AI가 메인테이너로서 확장하기에 이상적**이므로, 우리는 이 강점을 살려
   **Codex(ChatGPT)를 메인 메인테이너**로 두고 계약을 늘려간다.
   (설계 배경: [docs/architecture.ko.md](docs/architecture.ko.md), 에이전트 작업 규칙: [AGENTS.ko.md](AGENTS.ko.md))

## 구조

```
ArcSolve-Kit/
├── pyproject.toml
├── AGENTS.md                 # 모든 에이전트 공통 작업 규칙 (단일 출처)
├── CHANGELOG.md              # changelog.d/ 조각에서 합본
├── changelog.d/              # 체인지로그 조각 (서비스당 1개, 병렬 충돌 없음)
├── arcsolve/                 # 프레임워크 공통
│   ├── server.py             #   enabled 서비스를 합성해 단일 FastMCP 빌드
│   ├── service.py            #   Service = 모든 서비스의 균일 계약
│   ├── skill.py              #   Skill = 스킬의 균일 계약 + skills/ 자동 발견
│   ├── http.py               #   공유 HTTP 호출 + 에러 매핑
│   ├── oauth.py              #   범용 OAuth2(authcode+refresh) + 토큰 저장소
│   ├── catalog.py            #   레지스트리 → docs/services.md + docs/skills.md 자동 생성
│   ├── changelog.py          #   changelog.d/ → CHANGELOG.md 합본
│   ├── __main__.py           #   엔트리포인트 (serve / list / skills / auth / catalog / changelog)
│   └── services/             # ★ 서비스당 폴더 1개 (평면, 자동 발견)
│       ├── __init__.py       #   레지스트리 (services/ 자동 스캔 — 수동 편집 없음)
│       └── kakao/
│           ├── contract.py   #   ← 계약: 엔드포인트·스코프·요청/응답 모델
│           ├── tools.py      #   MCP 도구 (계약을 호출하는 얇은 래퍼)
│           └── README.md     #   서비스 가이드 (셋업·제약·공식 문서 링크)
├── skills/                   # ★ 스킬당 폴더 1개 (자동 발견, 데이터 트리)
│   └── academic-discovery/
│       ├── SKILL.md          #   frontmatter(name·description·allowed-tools) + 워크플로
│       └── README.md         #   스킬 가이드 + 계약 출처 + 필요 MCP 도구
├── docs/                     # 횡단 문서 (서비스/스킬 수와 무관하게 고정)
│   ├── architecture.md
│   ├── adding-a-service.md
│   ├── adding-a-skill.md
│   ├── providers.md          #   구현 대상 매니페스트 (공식 문서 링크 묶음)
│   ├── services.md           #   자동 생성 카탈로그 (MCP 도구)
│   └── skills.md             #   자동 생성 카탈로그 (스킬)
└── tests/
```

설계 원칙: **계약(`contract.py`)과 도구(`tools.py`)를 물리적으로 분리** → 서비스가 명확히
구분되면서도 구조는 균일하고, "공식 API 계약 기반 자체 클라이언트"임이 코드로 증명된다.

## 빠른 시작

```bash
# 1) 설치
uv pip install -e ".[dev]"      # 또는: pip install -e ".[dev]"

# 2) 자격증명 (.env.example 참고)
cp .env.example .env            # KAKAO_REST_API_KEY 등 채우기

# 3) 카카오 1회 인증 → refresh_token 저장
arcsolve auth kakao

# 4) 로컬 동작 확인
arcsolve                    # stdio MCP 서버 실행
```

MCP 호스트(Claude Desktop 등) 등록 예:

```json
{
  "mcpServers": {
    "arcsolve": {
      "command": "arcsolve",
      "args": ["serve", "kakao"],
      "env": {
        "KAKAO_REST_API_KEY": "...",
        "KAKAO_REFRESH_TOKEN": "..."
      }
    }
  }
}
```

## 원하는 모듈만 쓰기

설치는 한 패키지지만, **노출할 서비스는 골라서** 실행할 수 있다.

```bash
arcsolve list                 # 사용 가능한 서비스 확인
arcsolve serve kakao          # kakao만 노출
ARCSOLVE_SERVICES=kakao arcsolve   # 환경변수로도 선택 (호스트 env에 적기 좋음)
arcsolve                      # 미지정 시 전체
```

개별 모듈을 **자신의 MCP 서버에 임베드**하려면 등록 함수를 직접 호출하면 된다:

```python
from fastmcp import FastMCP
from arcsolve.services.kakao import SERVICE

mcp = FastMCP("my-app")
SERVICE.register(mcp)   # kakao 도구만 내 서버에 추가
```

## 새 서비스 추가 (폴더 하나)

1. `arcsolve/services/<name>/contract.py` — 엔드포인트 상수 + pydantic 요청/응답 모델
2. `arcsolve/services/<name>/tools.py` — `register(mcp)` 안에서 `@mcp.tool` 정의
3. `arcsolve/services/<name>/__init__.py` — `SERVICE = Service(...)` 선언

**레지스트리는 건드리지 않는다** — `services/`를 자동 스캔하므로 폴더만 떨구면 등록된다(병렬 충돌 없음).
자세한 절차·규칙은 [AGENTS.md](AGENTS.ko.md) / [docs/adding-a-service.md](docs/adding-a-service.ko.md).

## 스킬 (Skills)

MCP 도구가 "무엇이 있는가"라면, **스킬**은 "그걸 어떻게 잘 쓰는가"를 Claude에게 가르친다.
스킬은 `contract.py`를 import하지 않고 **실행 중인 ArcSolve MCP 도구를 오케스트레이션**한다 — 검증된
계약은 MCP 쪽 단일 출처로 남는다.

예시: [`academic-discovery`](skills/academic-discovery/README.md) — arXiv·Crossref·OpenAlex·PubMed·
Semantic Scholar를 가로질러 논문을 탐색·교차검증(단일 검색으로는 안 나오는 커버리지·인용 삼각검증).

```bash
arcsolve skills    # 사용 가능한 스킬 목록
```

새 스킬 추가는 [docs/adding-a-skill.md](docs/adding-a-skill.ko.md).

## 문서

- [AGENTS.md](AGENTS.ko.md) — 모든 에이전트(사람·AI) 공통 작업 규칙 (단일 출처)
- [아키텍처](docs/architecture.ko.md) — 계약/도구 분리, 단일 합성 호스트, "두 개의 OAuth"
- [새 서비스 추가](docs/adding-a-service.ko.md) — 3단계 + 서비스 README 템플릿
- [새 스킬 추가](docs/adding-a-skill.ko.md) — SKILL.md + 스킬 README 템플릿
- [구현 대상 매니페스트](docs/providers.md) — 공식 문서 링크 묶음 (병렬 작업 입력)
- [서비스 카탈로그](docs/services.md) — 도구 목록(자동 생성, `arcsolve catalog`)
- [스킬 카탈로그](docs/skills.md) — 스킬 목록(자동 생성)
- [i18n](docs/i18n.ko.md) — 양어 문서 규칙 (영어 정본, 한국어 번역)
- 서비스별 가이드: `arcsolve/services/<name>/README.md` (예: [kakao](arcsolve/services/kakao/README.md))
- 스킬별 가이드: `skills/<name>/README.md` (예: [academic-discovery](skills/academic-discovery/README.md))

## 보안

- 토큰은 `~/.arcsolve/credentials.json`에 **평문**으로 저장된다(파일 0600 / 디렉토리 0700). 공유 머신 주의.
- 인가코드 흐름은 공개 클라이언트 보호를 위해 **PKCE(S256)**를 사용한다.
- `*_REFRESH_TOKEN`을 호스트 설정 env에 직접 넣으면 평문 노출 경로가 늘어난다 — 가능하면 `auth`로 저장소를 쓰라.

## 라이선스

[Apache-2.0](LICENSE) · 기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.ko.md)
