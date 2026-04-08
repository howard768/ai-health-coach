"""Notification media generator.

Creates simple recovery badge images for rich push notifications.
Uses Pillow to draw colored circles with level indicators.
Images are saved to the media/ directory and served via FastAPI static files.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw

logger = logging.getLogger("meld.notification_media")

MEDIA_DIR = Path(__file__).resolve().parent.parent.parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)

# Recovery badge colors (matching DSColor.Status from the design system)
BADGE_COLORS = {
    "high": "#219E80",      # Green 500 (Success)
    "moderate": "#E5A626",  # Warning
    "low": "#D94040",       # Error
}

BADGE_SIZE = 200  # px


def generate_recovery_badge(level: str, base_url: str = "") -> str:
    """Generate a recovery badge PNG and return its URL.

    Args:
        level: "high", "moderate", or "low"
        base_url: Server base URL for constructing the media URL

    Returns:
        URL path to the generated badge image
    """
    level = level.lower()
    color = BADGE_COLORS.get(level, BADGE_COLORS["moderate"])
    filename = f"recovery-{level}.png"
    filepath = MEDIA_DIR / filename

    # Only generate if not already cached
    if not filepath.exists():
        img = Image.new("RGBA", (BADGE_SIZE, BADGE_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer circle (filled with recovery color)
        padding = 10
        draw.ellipse(
            [padding, padding, BADGE_SIZE - padding, BADGE_SIZE - padding],
            fill=color,
        )

        # Inner circle (white, for contrast)
        inner_padding = 40
        draw.ellipse(
            [inner_padding, inner_padding, BADGE_SIZE - inner_padding, BADGE_SIZE - inner_padding],
            fill="#FFFFFF",
        )

        # Level indicator in center
        # Draw a simple shape: checkmark area for high, dash for moderate, down arrow for low
        cx, cy = BADGE_SIZE // 2, BADGE_SIZE // 2
        if level == "high":
            # Upward triangle (good)
            draw.polygon(
                [(cx - 25, cy + 15), (cx, cy - 25), (cx + 25, cy + 15)],
                fill=color,
            )
        elif level == "low":
            # Downward triangle (needs rest)
            draw.polygon(
                [(cx - 25, cy - 15), (cx, cy + 25), (cx + 25, cy - 15)],
                fill=color,
            )
        else:
            # Horizontal bar (moderate)
            draw.rectangle(
                [cx - 25, cy - 6, cx + 25, cy + 6],
                fill=color,
            )

        img.save(filepath, "PNG")
        logger.info("Generated recovery badge: %s", filename)

    return f"{base_url}/media/{filename}"
