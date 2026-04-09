"""Unified food search service implementing the DOVA cascade.

DOVA principle: check databases before calling AI (40-60% cost savings).
Source priority: USDA lab (1.0) > USDA branded (0.95) > OFF (0.85) > AI estimate (0.6)
"""

import logging

from app.services.usda import usda_client
from app.services.openfoodfacts import off_client
from app.services.food_recognition import food_recognition

logger = logging.getLogger("meld.food_search")


class FoodSearchService:
    """Searches food databases with AI fallback."""

    async def search(self, query: str) -> list[dict]:
        """Search for food items using the DOVA cascade.

        1. Hit USDA first (most trusted, lab-analyzed data)
        2. If <3 USDA results, also hit Open Food Facts
        3. If zero total results, fall back to AI estimation
        """
        # Step 1: USDA (highest confidence)
        usda_results = await usda_client.search(query, page_size=10)
        logger.info("USDA returned %d results for '%s'", len(usda_results), query)

        # Step 2: If USDA has few results, supplement with OFF
        off_results = []
        if len(usda_results) < 3:
            off_results = await off_client.search(query, page_size=10)
            logger.info("OFF returned %d results for '%s'", len(off_results), query)

        # Merge and deduplicate
        all_results = usda_results + off_results
        all_results = self._deduplicate(all_results)

        # Step 3: AI fallback if no database results
        if not all_results:
            logger.info("No database results — falling back to AI estimation for '%s'", query)
            ai_results = food_recognition.recognize_from_text(query)
            all_results = ai_results

        return all_results[:15]  # Cap at 15 results

    def _deduplicate(self, items: list[dict]) -> list[dict]:
        """Remove duplicate food items by normalized name."""
        seen = set()
        unique = []
        for item in items:
            key = item["name"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique


food_search = FoodSearchService()
