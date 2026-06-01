"""서비스 레지스트리 — `services/` 하위 패키지를 자동 발견한다.

각 서비스 패키지(`arcsolve/services/<name>/__init__.py`)가 모듈 수준 `SERVICE: Service`를
노출하면 자동 등록된다. 수동 import/리스트 편집이 없으므로 **병렬로 서비스를 추가해도 충돌이 없다**.

격리·지연 로딩:
- `available()`는 모듈을 import하지 않고 폴더만 스캔한다(한 서비스가 깨져도 목록은 멀쩡).
- import는 서비스별로 try/except 격리한다 → 미완성/오류 서비스 하나가 전체를 죽이지 않는다.
- `select_services(names)`는 **선택된 것만 import**한다 → 개별 사용 시 나머지 서비스/의존성 미로딩.
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil

from arcsolve.service import Service

log = logging.getLogger(__name__)


def available() -> list[str]:
    """등록된 서비스 이름 — 모듈을 import하지 않고 폴더만 스캔."""
    return sorted(info.name for info in pkgutil.iter_modules(__path__) if info.ispkg)


def load_service(name: str) -> Service | None:
    """서비스 하나를 import해 SERVICE를 반환. 실패는 격리(경고 후 None)."""
    try:
        module = importlib.import_module(f"{__name__}.{name}")
    except Exception as e:  # noqa: BLE001 - 한 서비스 오류가 다른 서비스를 막지 않도록 격리
        log.warning("서비스 '%s' 로드 실패: %s", name, e)
        return None
    svc = getattr(module, "SERVICE", None)
    if not isinstance(svc, Service):
        log.warning("서비스 '%s'에 SERVICE가 없습니다.", name)
        return None
    return svc


def discover_services() -> list[Service]:
    """로드 가능한 모든 서비스(실패는 스킵)."""
    loaded = (load_service(n) for n in available())
    return sorted((s for s in loaded if s is not None), key=lambda s: s.name)


def select_services(names: list[str] | None = None) -> list[Service]:
    """노출할 서비스를 고른다.

    우선순위: 인자 `names` > 환경변수 `ARCSOLVE_SERVICES`(콤마구분) > 전체.
    이름이 주어지면 **그것만 import**한다(개별 사용 시 나머지 미로딩).
    """
    if names is None:
        env = os.environ.get("ARCSOLVE_SERVICES", "").strip()
        names = [n.strip() for n in env.split(",") if n.strip()] or None
    if not names:
        return discover_services()

    known = set(available())
    unknown = [n for n in names if n not in known]
    if unknown:
        raise ValueError(
            f"알 수 없는 서비스: {', '.join(unknown)} (사용 가능: {', '.join(sorted(known))})"
        )
    loaded = (load_service(n) for n in names)
    return [s for s in loaded if s is not None]
