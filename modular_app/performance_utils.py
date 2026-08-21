"""Small performance helpers shared by DICOM/UI modules."""
from __future__ import annotations

from typing import Any


def cache_get(cache: dict, key: Any, default: Any = None) -> Any:
    """Return a value and promote it to the newest position."""
    if key not in cache:
        return default
    value = cache.pop(key)
    cache[key] = value
    return value


def cache_put(cache: dict, key: Any, value: Any, max_entries: int) -> None:
    """Insert a value while keeping a deterministic bounded insertion-order cache."""
    if key in cache:
        cache.pop(key)
    cache[key] = value
    limit = max(1, int(max_entries))
    while len(cache) > limit:
        cache.pop(next(iter(cache)))


def cache_value_bytes(value: Any) -> int:
    """Return an approximate resident byte size for arrays and Qt images."""
    nbytes = getattr(value, "nbytes", None)
    if nbytes is not None:
        try:
            return max(0, int(nbytes))
        except (TypeError, ValueError):
            pass
    decoded = getattr(value, "_pixel_array", None)
    decoded_bytes = int(getattr(decoded, "nbytes", 0) or 0)
    pixel_data = getattr(value, "PixelData", None)
    raw_bytes = len(pixel_data) if isinstance(pixel_data, (bytes, bytearray, memoryview)) else 0
    if decoded_bytes or raw_bytes:
        return max(0, decoded_bytes + raw_bytes)
    for method_name in ("sizeInBytes", "byteCount"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return max(0, int(method()))
            except (TypeError, ValueError, RuntimeError):
                pass
    to_image = getattr(value, "toImage", None)
    if callable(to_image):
        try:
            image = to_image()
            for method_name in ("sizeInBytes", "byteCount"):
                method = getattr(image, method_name, None)
                if callable(method):
                    return max(0, int(method()))
            bytes_per_line = getattr(image, "bytesPerLine", None)
            height = getattr(image, "height", None)
            if callable(bytes_per_line) and callable(height):
                return max(0, int(bytes_per_line()) * int(height()))
        except (TypeError, ValueError, RuntimeError):
            pass
    width = getattr(value, "width", None)
    height = getattr(value, "height", None)
    depth = getattr(value, "depth", None)
    if callable(width) and callable(height) and callable(depth):
        try:
            return max(0, int(width()) * int(height()) * max(1, int(depth())) // 8)
        except (TypeError, ValueError, RuntimeError):
            pass
    return 0


def cache_bytes(cache: dict) -> int:
    """Return the current estimated byte weight of a cache."""
    return sum(cache_value_bytes(item) for item in cache.values())


def cache_put_sized(
    cache: dict,
    key: Any,
    value: Any,
    *,
    max_bytes: int,
    max_entries: int | None = None,
) -> bool:
    """Insert an LRU-like value while enforcing both byte and entry budgets."""
    size = cache_value_bytes(value)
    byte_limit = max(1, int(max_bytes))
    entry_limit = max(1, int(max_entries)) if max_entries is not None else None
    if size > byte_limit:
        cache.pop(key, None)
        return False
    cache_put(cache, key, value, max_entries=entry_limit or max(1, len(cache) + 1))
    while cache_bytes(cache) > byte_limit or (entry_limit is not None and len(cache) > entry_limit):
        oldest = next(iter(cache))
        if oldest == key and len(cache) == 1:
            cache.pop(oldest, None)
            return False
        cache.pop(oldest, None)
    return key in cache


def cache_put_array(cache: dict, key: Any, value: Any, max_bytes: int) -> bool:
    """Backward-compatible NumPy cache wrapper with a byte budget."""
    return cache_put_sized(cache, key, value, max_bytes=max_bytes)


def cache_drop_path(cache: dict, path: str, key_index: int = 0) -> None:
    """Remove entries whose tuple key starts with a given absolute path."""
    for key in list(cache):
        if isinstance(key, tuple) and len(key) > key_index and key[key_index] == path:
            cache.pop(key, None)
