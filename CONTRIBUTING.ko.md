# 기여 가이드

> [English](CONTRIBUTING.md) · **한국어**

<!-- i18n-source: CONTRIBUTING.md -->

ArcSolve-Kit에 기여해 주셔서 감사합니다. 작업 규칙의 단일 출처는 [AGENTS.ko.md](AGENTS.ko.md)입니다.

## 개발 셋업

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest -q          # 테스트
uv run ruff check .       # 린트
```

## 새 서비스 추가

[docs/adding-a-service.ko.md](docs/adding-a-service.ko.md)의 절차를 따릅니다. 요약:

1. `arcsolve/services/<name>/`에 `contract.py` + `tools.py` + `__init__.py` + `README.md`
2. `tests/test_<name>_contract.py` (네트워크 없는 계약 검증)
3. `changelog.d/<name>.md` (한 줄 변경 요약)
4. **레지스트리는 건드리지 않습니다** — 폴더만 떨구면 자동 발견됩니다.

## PR 체크리스트

- [ ] `uv run pytest -q` 통과
- [ ] `uv run ruff check .` 통과
- [ ] 계약(`contract.py`)의 모든 필드가 공식 문서 링크에서 확인됨 (환각 금지, 미확정은 `# TODO(provenance)`)
- [ ] 서비스 README에 "계약 출처" 공식 문서 링크 포함
- [ ] 새 의존성을 서비스 폴더에서 추가하지 않음 (필요 시 PR 설명에 명시 → 통합 시 `pyproject.toml` 반영)
- [ ] (자동) CI가 `catalog`/`changelog` 재생성 후 drift가 없는지 검사

## 문서 언어 (i18n)

문서는 양어다 — **영어가 정본**, 한국어(`*.ko.md`)는 번역이다. 정본을 고치면 같은 변경에서
`*.ko.md`도 갱신하거나 메인테이너/Codex가 갱신하게 둔다. [docs/i18n.ko.md](docs/i18n.ko.md) 참고.

## 커밋·브랜치

- 기본 브랜치에서 직접 작업하지 말고 브랜치를 파세요.
- 한 PR은 하나의 서비스/관심사로 좁게.
