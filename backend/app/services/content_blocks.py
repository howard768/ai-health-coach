"""Structured content blocks for chat responses.

The coach returns markdown text with optional inline tags that the client
renders as rich visual cards. Keeping this parser centralized means the
API contract and the client stay in sync.

Tag syntax:
    [[data:METRIC:VALUE:UNIT:SUBTITLE]]

Example:
    "Your sleep was solid. [[data:sleep_efficiency:91:%:above 7-day avg]]
     Take advantage of the recovery and train hard."

Parses to:
    [
      TextBlock("Your sleep was solid."),
      DataCardBlock(metric="sleep_efficiency", value="91", unit="%", ...),
      TextBlock("Take advantage of the recovery and train hard."),
    ]
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

# Match [[data:metric:value:unit:subtitle]] with non-greedy segment capture.
# Unit and subtitle may be empty; metric and value must be non-empty.
_DATA_TAG_RE = re.compile(r"\[\[data:([^:\]]+):([^:\]]+):([^:\]]*):([^\]]*)\]\]")


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    value: str


class DataCardBlock(BaseModel):
    type: Literal["data_card"] = "data_card"
    metric: str
    value: str
    unit: str
    subtitle: str


ContentBlock = Annotated[
    Union[TextBlock, DataCardBlock],
    Field(discriminator="type"),
]


def parse_content_blocks(raw: str) -> list[TextBlock | DataCardBlock]:
    """Split a raw LLM response into text and data-card blocks.

    Empty or whitespace-only text segments between tags are dropped so the
    client doesn't render blank bubbles.
    """
    blocks: list[TextBlock | DataCardBlock] = []
    pos = 0
    for match in _DATA_TAG_RE.finditer(raw):
        if match.start() > pos:
            text = raw[pos:match.start()].strip()
            if text:
                blocks.append(TextBlock(value=text))
        metric, value, unit, subtitle = match.groups()
        blocks.append(
            DataCardBlock(
                metric=metric.strip(),
                value=value.strip(),
                unit=unit.strip(),
                subtitle=subtitle.strip(),
            )
        )
        pos = match.end()
    if pos < len(raw):
        text = raw[pos:].strip()
        if text:
            blocks.append(TextBlock(value=text))
    if not blocks:
        # Empty input: return a single empty text block so downstream
        # code never has to handle the []-case specially.
        blocks.append(TextBlock(value=raw))
    return blocks


def flatten_to_markdown(raw: str) -> str:
    """Replace data tags with bold inline text so legacy clients still render.

    Used for the `content` field of chat responses. New clients read `blocks`;
    old clients (or history from before this change) read `content`.
    """
    def _replace(match: re.Match) -> str:
        _metric, value, unit, _subtitle = match.groups()
        body = f"{value.strip()}{unit.strip()}" if unit.strip() else value.strip()
        return f"**{body}**"
    return _DATA_TAG_RE.sub(_replace, raw)


def sanitize_output(raw: str) -> str:
    """Safety net for the no-em-dash rule.

    The system prompt forbids em dashes (—) but the model occasionally
    slips. Replace any survivors with a comma-space, which is the closest
    grammatical substitute. Applied before parsing or persisting so we
    never store em dashes downstream.
    """
    # Handle " — " (spaced) first to avoid double-spacing, then bare —.
    cleaned = raw.replace(" — ", ", ").replace("—", ", ")
    # Collapse any double commas that resulted from adjacent substitutions.
    cleaned = re.sub(r",\s*,", ",", cleaned)
    return cleaned
