from __future__ import annotations


def display_measurement_source(value: object) -> str:
    """Present the measurement origin consistently in UI and exports."""
    source = str(value or "").strip().lower()
    return {
        "left": "Sol",
        "right": "Sağ",
        "viewer": "Görüntüleyici",
    }.get(source, str(value or "—").strip() or "—")
