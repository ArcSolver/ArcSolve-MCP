# 새 스킬 추가하기

> [English](adding-a-skill.md) · **한국어**

<!-- i18n-source: adding-a-skill.md -->

스킬 하나 = **폴더 하나** (`skills/<name>/`). 스킬은 import되는 코드가 아니라 **배포되는 데이터**다 —
`SKILL.md`로 "MCP 도구를 어떻게 엮어 쓰는가"를 담는다. 공통 프레임워크(`skill`/`catalog`)는 건드리지 않는다.

> **핵심(AGENTS.md 규칙 2-2):** 스킬은 `contract.py`를 import하지 않고 상류 API를 직접 치지도 않는다.
> 검증된 계약은 MCP 서비스에 단일 출처로 남고, 스킬은 **실행 중인 ArcSolve MCP 서버의 도구를
> 오케스트레이션**한다. 스킬 = 도구를 잘 엮는 지시 + (선택) 얇은 stdlib 헬퍼.

## 구성

```
skills/<name>/
├── SKILL.md        # 계약: frontmatter(name·description·allowed-tools) + 워크플로 지시 본문
├── scripts/        # (선택) 순수 헬퍼 — stdlib 전용, 상류 API 직접 호출 X
├── references/     # (선택) 점진 로드용 레퍼런스 문서
└── README.md       # 운영 가이드 + "계약 출처" + "필요 MCP 도구"
```

### 1. `SKILL.md` — frontmatter + 본문

```markdown
---
name: example-discovery
description: 여러 출처를 가로질러 X를 탐색·교차검증한다. ~할 때 사용한다(트리거). (한 줄로 — frontmatter는 최소 YAML)
allowed-tools:
  - foo_search
  - foo_get
  - bar_search
---

# Example discovery

## 언제 쓰나
...(트리거 상황)

## 워크플로
1. 소스별 질의 변환 ...
2. 멀티소스 검색 후 식별자로 dedup ...
3. ...

## 경계
- ~까지만. 합성·작성은 안 한다(그건 다른 스킬).
```

frontmatter 규칙:
- `name`: 폴더명과 동일, 소문자·하이픈.
- `description`: **3인칭으로 "무엇을 + 언제(트리거)"**. 과대선언 금지(이게 공개 약속 = 계약이다).
- `allowed-tools`: 오케스트레이션할 **ArcSolve MCP 도구명**(예: `arxiv_search`). 정적 테스트가
  실재 도구(`docs/services.md` 카탈로그)와 대조하므로 **반드시 실재 도구명**이어야 한다.

### 2. 본문 — 워크플로 지시

Claude가 따를 절차를 적는다. 사실 부분(도구명·파라미터·명령 문법)은 출처를 추적하고,
불확실하면 `TODO(provenance)`를 남긴다. 워크플로/판단은 외부 출처가 없으므로 **eval로 품질을 검증**한다.

### 3. (선택) `scripts/` · `references/`

- `scripts/`: 결정적 헬퍼(포맷팅·dedup 등)만. **표준 라이브러리만** 쓰고 `arcsolve`를 import하지 않는다.
  API 호출은 MCP 도구가 담당한다.
- `references/`: 길어서 본문에 다 못 넣는 자료(소스별 커버리지·질의 문법 등). 필요 시 점진 로드된다.

### 마무리

- `tests/test_<name>_skill.py` → **정적 불변식만**: frontmatter 필수 필드·참조 해소·`allowed-tools`가
  실재 도구명과 일치(네트워크·모델 없음).
- `evals/`(또는 `skills/<name>/evals/`) → **품질 게이트**: skill-creator 하니스로 "Claude를 옳게
  행동시키는가"를 검증(비결정적, 모델 호출 — pytest CI와 별개).
- `changelog.d/skill-<name>.md` → 한 줄 요약 (서비스와 이름 충돌 방지로 `skill-` prefix).
- 통합 단계(개별 에이전트 아님)에서 `arcsolve catalog` 실행 → `docs/skills.md` 재생성.

## 스킬 README 템플릿 (필수)

문서는 **스킬 옆에 둔다**: `skills/<name>/README.md`. provenance 테스트가 "계약 출처"와
"필요 MCP 도구" 섹션을 검사한다.

```markdown
# <Skill>
한 줄 설명(성격: 탐색/요약/...).

## 계약 출처 (공식 문서)
스킬이 오케스트레이션하는 MCP 서비스의 검증된 계약에 기댄다(스킬은 계약을 재정의하지 않는다).
- <service A> API: <url>
- <service B> API: <url>

## 필요 MCP 도구
이 스킬은 ArcSolve MCP 서버에서 아래 도구가 노출돼 있어야 한다(`allowed-tools`와 일치).
- `foo_search`, `foo_get` — <service A>
- `bar_search` — <service B>
> 셋업: `arcsolve serve <service A> <service B>` (또는 ARCSOLVE_SERVICES)

## 범위 / 경계
- 포함 = ... / 제외(다른 스킬) = ...
```

## 어디에 무엇을 쓰나 (요약)

| 문서 | 위치 | 출처(누가 진실인가) |
|------|------|------|
| 검증된 API 계약 | MCP `services/<x>/contract.py` | **코드** — 스킬은 재정의 안 함 |
| 스킬 본체(워크플로·트리거) | `skills/<name>/SKILL.md` | 스킬당 1개 |
| 스킬 운영 가이드 | `skills/<name>/README.md` | 스킬당 1개 |
| 스킬 카탈로그 | `docs/skills.md` | **자동 생성** (`arcsolve catalog`) |
| 체인지로그 | `changelog.d/skill-<name>.md` → `CHANGELOG.md` | 조각으로 쓰고 **합본** |
| 공통 작업 규칙 | `AGENTS.md` | 모든 에이전트의 단일 출처 |
