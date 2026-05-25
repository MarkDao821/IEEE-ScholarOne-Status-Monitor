from __future__ import annotations

from typing import Protocol

from ..models import AppConfig, JournalAccount, ManuscriptRecord


class JournalScraper(Protocol):
    def scrape(
        self,
        journal: JournalAccount,
        config: AppConfig,
        debug: bool = False,
    ) -> list[ManuscriptRecord]:
        pass
