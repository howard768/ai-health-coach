"""USDA FoodData Central API client.

Free API, no auth needed for low volume (DEMO_KEY).
Source priority: SR Legacy (lab-analyzed) > Branded.
"""

import logging
import httpx

from app.config import settings

logger = logging.getLogger("meld.usda")

USDA_BASE = "https://api.nal.usda.gov/fdc/v1"

# Nutrient IDs for extraction
NUTRIENT_IDS = {
    1008: "calories",   # Energy (kcal)
    1003: "protein",    # Protein (g)
    1005: "carbs",      # Carbohydrate (g)
    1004: "fat",        # Total fat (g)
}

PROCESSED_KEYWORDS = {"chips", "candy", "soda", "cookie", "cake", "donut", "fries", "nugget", "hot dog"}
WHOLE_KEYWORDS = {"raw", "fresh", "organic", "whole", "plain"}


class USDAClient:
    """Searches the USDA FoodData Central database."""

    def __init__(self):
        self.api_key = getattr(settings, "usda_api_key", "DEMO_KEY") or "DEMO_KEY"

    async def search(self, query: str, page_size: int = 10) -> list[dict]:
        """Search USDA for food items.

        Returns normalized food item dicts sorted by relevance,
        with SR Legacy (lab-analyzed) results first.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{USDA_BASE}/foods/search",
                    params={"api_key": self.api_key},
                    json={
                        "query": query,
                        "pageSize": page_size,
                        "dataType": ["SR Legacy", "Survey (FNDDS)", "Branded"],
                    },
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            # httpx.HTTPError covers network, timeout, and HTTP status errors.
            # ValueError covers JSON decode failures.
            logger.error("USDA search failed: %s", e)
            return []

        results = []
        for food in data.get("foods", []):
            item = self._normalize_food(food)
            if item:
                results.append(item)

        # Sort: SR Legacy first, then Branded
        results.sort(key=lambda x: 0 if x["data_source"] == "usda" else 1)
        return results

    def _normalize_food(self, food: dict) -> dict | None:
        """Convert USDA API response to our FoodItem format."""
        name = food.get("description", "")
        if not name:
            return None

        # Extract nutrients
        nutrients = {}
        for nutrient in food.get("foodNutrients", []):
            nid = nutrient.get("nutrientId")
            if nid in NUTRIENT_IDS:
                nutrients[NUTRIENT_IDS[nid]] = nutrient.get("value", 0)

        # Determine data source
        data_type = food.get("dataType", "")
        if data_type in ("SR Legacy", "Survey (FNDDS)"):
            data_source = "usda"
            confidence = 1.0
        else:
            data_source = "usda_branded"
            confidence = 0.95

        # Determine quality
        name_lower = name.lower()
        if any(kw in name_lower for kw in WHOLE_KEYWORDS) or data_source == "usda":
            quality = "whole"
        elif any(kw in name_lower for kw in PROCESSED_KEYWORDS):
            quality = "processed"
        else:
            quality = "mixed"

        # Serving size
        serving = food.get("servingSize")
        serving_unit = food.get("servingSizeUnit", "g")
        serving_size = f"{serving}{serving_unit}" if serving else "100g"

        return {
            "name": name.title(),
            "serving_size": serving_size,
            "serving_count": 1.0,
            "calories": int(nutrients.get("calories", 0)),
            "protein": round(nutrients.get("protein", 0), 1),
            "carbs": round(nutrients.get("carbs", 0), 1),
            "fat": round(nutrients.get("fat", 0), 1),
            "quality": quality,
            "data_source": data_source,
            "confidence": confidence,
        }


usda_client = USDAClient()
