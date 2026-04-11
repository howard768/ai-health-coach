"""Claude Vision food recognition service.

Sends food photos to Claude Vision API for identification and nutrition estimation.
Also supports text-based nutrition estimation as an AI fallback for food search.

All outputs follow the wiki rules:
- Quality as whole/mixed/processed (not moralistic good/bad)
- 4th grade reading level for food names
- Confidence 0-1 for each item
"""

import json
import logging

import anthropic
from app.config import settings

logger = logging.getLogger("meld.food_recognition")

PHOTO_RECOGNITION_PROMPT = """Identify all food items visible in this photo.

For each item, estimate:
- name: simple, common name (4th grade reading level)
- serving_size: natural serving description (e.g., "1 medium breast", "1 cup", "2 slices")
- calories: estimated kcal for that serving
- protein: grams
- carbs: grams
- fat: grams
- quality: "whole" (unprocessed, natural), "mixed" (some processing), or "processed" (heavily processed)
- confidence: 0.0 to 1.0 (how sure you are about the identification and portions)

Be practical, not perfect. Round to nearest 5 calories. Err on the side of reasonable portions.

Respond with ONLY a JSON array, no other text:
[{"name": "...", "serving_size": "...", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "quality": "...", "confidence": 0.0}]"""

TEXT_RECOGNITION_PROMPT = """Estimate the nutrition for this food: {query}

Assume a standard single serving. Provide your best estimate.

Respond with ONLY a JSON array, no other text:
[{"name": "...", "serving_size": "...", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "quality": "whole|mixed|processed", "confidence": 0.0}]"""


class FoodRecognitionService:
    """Identifies food from photos or text using Claude Vision API."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def recognize_from_photo(self, image_base64: str, media_type: str = "image/jpeg") -> list[dict]:
        """Identify food items from a photo using Claude Vision.

        Args:
            image_base64: Base64-encoded image data
            media_type: MIME type (image/jpeg, image/png, etc.)

        Returns:
            List of food item dicts with name, serving_size, calories, macros, quality, confidence
        """
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {"type": "text", "text": PHOTO_RECOGNITION_PROMPT},
                    ],
                }],
            )

            result_text = response.content[0].text
            items = json.loads(result_text)

            # Ensure all items have required fields with defaults
            for item in items:
                item.setdefault("data_source", "ai_estimate")
                item.setdefault("confidence", 0.7)
                item.setdefault("quality", "mixed")

            logger.info("Recognized %d food items from photo", len(items))
            return items

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Vision response as JSON: %s", e)
            return []
        except anthropic.APIError as e:
            logger.error("Food recognition failed: %s", e)
            return []

    def recognize_from_text(self, query: str) -> list[dict]:
        """Estimate nutrition from a text description (AI fallback for search).

        Used when USDA and OFF have no results for a food query.
        """
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": TEXT_RECOGNITION_PROMPT.format(query=query),
                }],
            )

            result_text = response.content[0].text
            items = json.loads(result_text)

            for item in items:
                item.setdefault("data_source", "ai_estimate")
                item.setdefault("confidence", 0.6)

            logger.info("AI estimated nutrition for: %s", query)
            return items

        except (anthropic.APIError, json.JSONDecodeError) as e:
            logger.error("Text recognition failed: %s", e)
            return []


# Singleton
food_recognition = FoodRecognitionService()
