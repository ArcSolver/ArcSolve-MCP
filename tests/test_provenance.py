"""provenance(출처) 강제 — 모든 서비스가 공식 문서 출처를 코드/문서에 갖는지 검증."""

from pathlib import Path

import arcsolve.services as services_pkg
from arcsolve.services import discover_services

PKG_DIR = Path(services_pkg.__file__).parent


def test_every_service_declares_docs_url():
    for svc in discover_services():
        assert svc.docs_url.startswith("http"), f"{svc.name}: docs_url 누락"


def test_every_service_readme_cites_source():
    for svc in discover_services():
        readme = PKG_DIR / svc.name / "README.md"
        assert readme.exists(), f"{svc.name}: README.md 없음"
        text = readme.read_text(encoding="utf-8")
        # 양어 정책(docs/i18n.md): 영어 정본 'Contract sources' 또는 한국어 '계약 출처' 둘 다 허용.
        assert ("Contract sources" in text) or ("계약 출처" in text), (
            f"{svc.name}: README에 'Contract sources'/'계약 출처' 섹션 없음"
        )
        host = svc.docs_url.split("/")[2]
        assert host in text, f"{svc.name}: README에 출처 호스트({host}) 인용 없음"
