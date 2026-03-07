from __future__ import annotations

import re

from app.domain.models.business import Business


class BusinessNormalizer:
    """Cleans and deduplicates a list of scraped Business records."""

    def normalize(self, businesses: list[Business]) -> list[Business]:
        cleaned = [self._clean(b) for b in businesses]
        return self._deduplicate(cleaned)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clean(self, business: Business) -> Business:
        return Business(
            id=business.id,
            scraping_job_id=business.scraping_job_id,
            name=business.name.strip(),
            category=business.category.strip().lower(),
            zone=business.zone.strip(),
            address=business.address.strip() if business.address else None,
            phone=self._normalize_phone(business.phone),
            website=business.website.strip() if business.website else None,
            google_maps_url=business.google_maps_url,
            rating=business.rating,
            review_count=business.review_count,
            latitude=business.latitude,
            longitude=business.longitude,
            is_verified=business.is_verified,
            scraped_at=business.scraped_at,
            created_at=business.created_at,
        )

    def _normalize_phone(self, phone: str | None) -> str | None:
        if phone is None:
            return None
        phone = phone.strip()
        has_plus = phone.startswith("+")
        digits_and_spaces = re.sub(r"[^\d\s]", "", phone).strip()
        return ("+" + digits_and_spaces) if has_plus else digits_and_spaces or None

    def _deduplicate(self, businesses: list[Business]) -> list[Business]:
        seen: set[tuple[str, str | None]] = set()
        result: list[Business] = []
        for biz in businesses:
            key = (biz.name.lower(), biz.address.lower() if biz.address else None)
            if key not in seen:
                seen.add(key)
                result.append(biz)
        return result
