from __future__ import annotations

import re
from dataclasses import dataclass


ALLOWED_SOURCE_SECTIONS = {"requirements", "description"}
MAX_SENTENCE_LENGTH = 180

BULLET_PREFIX_PATTERN = re.compile(
    r"^\s*(?:[-*•]|[0-9]+[.)、]|（[0-9]+）|\([0-9]+\))\s*"
)
INLINE_ITEM_PATTERN = re.compile(
    r"(?:(?<=\s)|(?<=[。；;\n\r]))(?:[-*•]|[0-9]+[.)、]|（[0-9]+）|\([0-9]+\))\s+"
)
SECONDARY_SPLIT_PATTERN = re.compile(r"[；;\n\r]+")


@dataclass(frozen=True)
class SentenceSpan:
    source_section: str
    sentence: str
    start: int
    end: int


def split_text_sections(
    sections: dict[str, object],
    *,
    max_sentence_length: int = MAX_SENTENCE_LENGTH,
) -> list[SentenceSpan]:
    sentences: list[SentenceSpan] = []
    for source_section in ("requirements", "description"):
        value = sections.get(source_section)
        if not isinstance(value, str) or not value.strip():
            continue
        sentences.extend(
            split_text(
                value,
                source_section=source_section,
                max_sentence_length=max_sentence_length,
            )
        )
    return sentences


def split_text(
    text: str,
    *,
    source_section: str,
    max_sentence_length: int = MAX_SENTENCE_LENGTH,
) -> list[SentenceSpan]:
    if source_section not in ALLOWED_SOURCE_SECTIONS:
        raise ValueError("source_section must be requirements or description")

    sentences: list[SentenceSpan] = []
    for start, end in _primary_ranges(text):
        for sub_start, sub_end in _split_long_range(
            text,
            start=start,
            end=end,
            max_sentence_length=max_sentence_length,
        ):
            sentence, clean_start, clean_end = _clean_sentence_span(
                text[sub_start:sub_end],
                sub_start,
            )
            if sentence:
                sentences.append(
                    SentenceSpan(
                        source_section=source_section,
                        sentence=sentence,
                        start=clean_start,
                        end=clean_end,
                    )
                )
    return sentences


def _primary_ranges(text: str) -> list[tuple[int, int]]:
    cut_points = set()
    index = 0
    while index < len(text):
        char = text[index]
        if char in "。；;\n\r" or _is_sentence_period(text, index):
            cut_points.add(index + 1)
        index += 1
    for match in INLINE_ITEM_PATTERN.finditer(text):
        cut_points.add(match.start())

    ranges: list[tuple[int, int]] = []
    cursor = 0
    for cut_point in sorted(point for point in cut_points if 0 < point <= len(text)):
        if cursor < cut_point:
            ranges.append((cursor, cut_point))
        cursor = cut_point
    if cursor < len(text):
        ranges.append((cursor, len(text)))
    return ranges


def _is_sentence_period(text: str, index: int) -> bool:
    if text[index] != ".":
        return False
    previous_char = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    if previous_char.isdigit() and (next_char.isspace() or next_char == ""):
        return False
    return True


def _split_long_range(
    text: str,
    *,
    start: int,
    end: int,
    max_sentence_length: int,
) -> list[tuple[int, int]]:
    if len(text[start:end].strip()) <= max_sentence_length:
        return [(start, end)]
    ranges: list[tuple[int, int]] = []
    cursor = start
    for match in SECONDARY_SPLIT_PATTERN.finditer(text, start, end):
        if cursor < match.start():
            ranges.append((cursor, match.start()))
        cursor = match.end()
    if cursor < end:
        ranges.append((cursor, end))
    return ranges or [(start, end)]


def _clean_sentence_span(raw_sentence: str, start: int) -> tuple[str, int, int]:
    left_trim = len(raw_sentence) - len(raw_sentence.lstrip())
    right_trimmed_length = len(raw_sentence.rstrip())
    clean_start = start + left_trim
    clean_end = start + right_trimmed_length
    sentence = raw_sentence.strip()

    bullet_match = BULLET_PREFIX_PATTERN.match(sentence)
    if bullet_match:
        prefix_end = bullet_match.end()
        clean_start += prefix_end
        sentence = sentence[prefix_end:]
        nested_left_trim = len(sentence) - len(sentence.lstrip())
        clean_start += nested_left_trim
        sentence = sentence.strip()

    return sentence, clean_start, clean_end
