# changelog.d — 체인지로그 조각

병렬 충돌을 막기 위해, 각 서비스/변경은 **여기 `<name>.md` 파일 하나에 자기 변경만** 적는다.
(에이전트는 `CHANGELOG.md` 본체를 직접 건드리지 않는다.)

- 형식: Markdown 불릿. 예) `- **kakao**: 도구 X 추가`
- 통합 단계에서 `arcsolve-mcp changelog`가 모든 조각을 `CHANGELOG.md`의 `[Unreleased]`로 합본한다.
- 릴리즈 시: `[Unreleased]`를 버전 섹션으로 옮기고 조각 파일들을 비운다.

이 `README.md`는 합본에서 제외된다.
