"""
Auditoria rápida de testes de scrapers.

Mostra, para cada scraper registrado:
- se existe teste dedicado (tests/test_<scraper_name>_scraper.py)
- se passa no quickcheck offline (execução sem rede)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from application.domain.services.scraper_factory import ScraperFactory
from application.domain.services.scraper_registry import ScraperRegistry


def _run_quickcheck(scraper_name: str) -> Tuple[bool, str]:
    scraper = ScraperFactory.create(scraper_name)
    if scraper is None:
        return False, "scraper não encontrado no registry"

    if hasattr(scraper, "fetch_page"):
        setattr(scraper, "fetch_page", lambda *args, **kwargs: None)
    if hasattr(scraper, "fetch_json"):
        setattr(scraper, "fetch_json", lambda *args, **kwargs: None)

    try:
        items = scraper.scrape()
        if not isinstance(items, list):
            return False, "scrape() não retornou list"
        return True, "ok"
    except Exception as exc:
        return False, f"erro: {exc}"


def main() -> int:
    load_all_scrapers()
    tests_dir = ROOT_DIR / "tests"
    names = sorted(ScraperRegistry.get_all_scrapers().keys())

    if not names:
        print("Nenhum scraper registrado.")
        return 1

    rows: list[tuple[str, str, str]] = []
    failures = 0

    for name in names:
        dedicated_file = tests_dir / f"test_{name}_scraper.py"
        dedicated_status = "sim" if dedicated_file.exists() else "nao"

        ok, quick_msg = _run_quickcheck(name)
        quick_status = "ok" if ok else quick_msg
        if not ok:
            failures += 1

        rows.append((name, dedicated_status, quick_status))

    name_width = max(len("SCRAPER"), max(len(row[0]) for row in rows))
    dedicated_width = len("TESTE_DEDICADO")
    quick_width = max(len("QUICKCHECK"), max(len(row[2]) for row in rows))

    header = (
        f"{'SCRAPER'.ljust(name_width)} | "
        f"{'TESTE_DEDICADO'.ljust(dedicated_width)} | "
        f"{'QUICKCHECK'.ljust(quick_width)}"
    )
    separator = "-" * len(header)
    print(header)
    print(separator)
    for name, dedicated, quick in rows:
        print(
            f"{name.ljust(name_width)} | "
            f"{dedicated.ljust(dedicated_width)} | "
            f"{quick.ljust(quick_width)}"
        )

    print()
    print(f"Resumo: {len(rows)} scrapers, {failures} falhas no quickcheck offline.")
    if os.getenv("FAIL_ON_MISSING_DEDICATED_TEST") == "1":
        missing = [name for name, dedicated, _ in rows if dedicated != "sim"]
        if missing:
            print(f"Sem teste dedicado: {', '.join(missing)}")
            return 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
