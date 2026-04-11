"""Open Food Facts API client.

Free, no auth needed. Provides barcode lookup and text search.
Uses NOVA group for food quality classification.
"""

import logging
import httpx

logger = logging.getLogger("meld.openfoodfacts")

OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PRODUCT = "https://world.openfoodfacts.org/api/v2/product"


class OpenFoodFactsClient:
    """Searches Open Food Facts database and looks up products by barcode."""

    async def search(self, query: str, page_size: int = 10) -> list[dict]:
        """Text search for food items on Open Food Facts."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    OFF_SEARCH,
                    params={
                        "search_terms": query,
                        "json": 1,
                        "page_size": page_size,
                        "fields": "product_name,nutriments,serving_size,nova_group,brands",
                    },
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error("OFF search failed: %s", e)
            return []

        results = []
        for product in data.get("products", []):
            item = self._normalize_product(product)
            if item:
                results.append(item)

        return results

    async def get_by_barcode(self, barcode: str) -> dict | None:
        """Look up a product by barcode (EAN-13, UPC-A, etc.)."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{OFF_PRODUCT}/{barcode}",
                    params={"fields": "product_name,nutriments,serving_size,nova_group,brands"},
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error("OFF barcode lookup failed for %s: %s", barcode, e)
            return None

        if data.get("status") != 1:
            return None

        return self._normalize_product(data.get("product", {}))

    def _normalize_product(self, product: dict) -> dict | None:
        """Convert OFF product data to our FoodItem format."""
        name = product.get("product_name", "")
        if not name:
            return None

        brand = product.get("brands", "")
        if brand:
            name = f"{name} ({brand})"

        nutrients = product.get("nutriments", {})

        # Prefer per-serving values, fall back to per-100g
        calories = nutrients.get("energy-kcal_serving") or nutrients.get("energy-kcal_100g", 0)
        protein = nutrients.get("proteins_serving") or nutrients.get("proteins_100g", 0)
        carbs = nutrients.get("carbohydrates_serving") or nutrients.get("carbohydrates_100g", 0)
        fat = nutrients.get("fat_serving") or nutrients.get("fat_100g", 0)

        serving_size = product.get("serving_size", "100g")

        # Quality from NOVA group
        nova = product.get("nova_group")
        if nova in (1, 2):
            quality = "whole"
        elif nova == 3:
            quality = "mixed"
        elif nova == 4:
            quality = "processed"
        else:
            quality = "mixed"

        return {
            "name": name,
            "serving_size": serving_size,
            "serving_count": 1.0,
            "calories": int(calories or 0),
            "protein": round(float(protein or 0), 1),
            "carbs": round(float(carbs or 0), 1),
            "fat": round(float(fat or 0), 1),
            "quality": quality,
            "data_source": "off",
            "confidence": 0.85,
        }


off_client = OpenFoodFactsClient()
