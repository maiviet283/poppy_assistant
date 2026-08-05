from __future__ import annotations


def is_true(value) -> bool:
    """Normalise a confirmation flag; the model may send a bool or a string."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def missing_fields(fields: dict, required: list[tuple[str, str]]) -> list[str]:
    """Return the human labels of required fields that are missing or blank.

    ``required`` is a list of (key, human_label) pairs; ``fields`` holds the
    normalised values to check.
    """
    return [label for key, label in required if not (fields.get(key) or "").strip()]
