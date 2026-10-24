"""Configurable service limits and bounded JSON validation; no database operations."""

import json
import math
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError


@dataclass(frozen=True)
class AchievementLimits:
    max_skills_per_event: int = 256
    max_evidence_bytes: int = 262144
    max_event_id_length: int = 255
    max_evidence_reference_length: int = 4096
    bulk_batch_size: int = 100
    max_evidence_depth: int = 64
    max_evidence_nodes: int = 50000
    retry_attempts: int = 3
    retry_base_delay: float = 0.025
    retry_max_delay: float = 0.25


def get_achievement_limits():
    configured = getattr(settings, "ACHIEVEMENT_LIMITS", {})
    defaults = asdict(AchievementLimits())
    if not isinstance(configured, dict) or set(configured) - defaults.keys():
        raise ImproperlyConfigured("ACHIEVEMENT_LIMITS must be a dictionary of supported limit names.")
    values = defaults | configured
    for key, value in values.items():
        if key in ("retry_base_delay", "retry_max_delay"):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 2:
                raise ImproperlyConfigured(f"ACHIEVEMENT_LIMITS.{key} must be finite and between 0 and 2 seconds.")
        elif type(value) is not int or value < 1:
            raise ImproperlyConfigured(f"ACHIEVEMENT_LIMITS.{key} must be a positive integer.")
    if values["max_event_id_length"] > 255:
        raise ImproperlyConfigured("max_event_id_length cannot exceed the existing 255-character database field.")
    if values["max_evidence_bytes"] < 2:
        raise ImproperlyConfigured("max_evidence_bytes must allow at least an empty JSON object (2 bytes).")
    if values["retry_attempts"] > 5:
        raise ImproperlyConfigured("retry_attempts cannot exceed 5 total attempts.")
    if values["retry_base_delay"] > values["retry_max_delay"]:
        raise ImproperlyConfigured("retry_base_delay cannot exceed retry_max_delay.")
    return AchievementLimits(**values)


def validate_text(value, field, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError({field: f"Expected a string of at most {maximum} characters."})
    if "\x00" in value:
        raise ValidationError({field: "NUL characters are not supported."})
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError({field: "Expected valid Unicode text."}) from exc


def bounded_evidence(evidence, limits):
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict):
        raise ValidationError({"evidence": "Expected a JSON object."})
    pending = [(evidence, 1)]
    nodes = minimum_bytes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if nodes > limits.max_evidence_nodes or depth > limits.max_evidence_depth:
            raise ValidationError({"evidence": "JSON exceeds the configured nesting or node limit."})
        if isinstance(value, (dict, list, tuple)):
            if len(value) + len(pending) > limits.max_evidence_nodes - nodes:
                raise ValidationError({"evidence": "JSON exceeds the configured node limit."})
            if isinstance(value, dict):
                for key, child in value.items():
                    validate_text(key, "evidence", limits.max_evidence_bytes)
                    minimum_bytes += len(key)
                    pending.append((child, depth + 1))
            else:
                pending.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            validate_text(value, "evidence", limits.max_evidence_bytes)
            minimum_bytes += len(value)
        elif value is None or type(value) in (bool, int):
            minimum_bytes += 1
        elif type(value) is float and math.isfinite(value):
            minimum_bytes += 1
        else:
            raise ValidationError({"evidence": "Expected finite JSON values and string object keys."})
        if minimum_bytes > limits.max_evidence_bytes:
            raise ValidationError({"evidence": f"JSON exceeds {limits.max_evidence_bytes} serialized bytes."})
    try:
        chunks = []
        size = 0
        encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        for chunk in encoder.iterencode(evidence):
            size += len(chunk)
            if size > limits.max_evidence_bytes:
                raise ValidationError({"evidence": f"JSON exceeds {limits.max_evidence_bytes} serialized bytes."})
            chunks.append(chunk)
        return json.loads("".join(chunks))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationError({"evidence": "Expected bounded, JSON-serializable evidence."}) from exc
