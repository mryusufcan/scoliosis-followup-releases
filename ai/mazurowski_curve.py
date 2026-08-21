"""Mask-centre Cobb geometry adapted from the Apache-2.0 Mazurowski project."""
from __future__ import annotations

import cv2
import numpy as np
from scipy.signal import find_peaks


def cobb_from_mask(mask: np.ndarray, box: np.ndarray) -> tuple[float, tuple[tuple[float, float], ...]]:
    """Return the largest adjacent tangent angle and four image-space points."""
    binary = np.asarray(mask) >= 0.5
    rows = np.where(binary.any(axis=1))[0]
    if rows.size < 40:
        raise ValueError("Omurga maskesi Cobb eğrisi oluşturmak için çok kısa.")
    centers = np.asarray([(np.flatnonzero(binary[row])[0] + np.flatnonzero(binary[row])[-1]) // 2 for row in rows])
    trim = int(len(rows) * 0.02)
    if trim:
        rows, centers = rows[trim:-trim], centers[trim:-trim]
    ratio = 572.0 / max(float(box[3] - box[1]), 1.0)
    row_offset, column_offset = int(box[1]), int(box[0])
    x_fit = (rows - row_offset) * ratio
    y_fit = (centers - column_offset) * ratio
    curve = np.poly1d(np.polyfit(x_fit, y_fit, 10))
    x_fit = np.asarray(sorted(set(int(item) for item in x_fit)), dtype=np.int64)
    first = np.polyder(curve, 1)
    second = np.polyder(curve, 2)
    slopes = first(x_fit)
    curvatures = second(x_fit)
    extrema, _ = find_peaks(np.abs(slopes))
    breaks = [0]
    for index in range(len(slopes) - 1):
        if slopes[index] * slopes[index + 1] <= 0 and index - breaks[-1] > 35 and x_fit[-1] - x_fit[index] > 35:
            breaks.append(index)
        elif index - breaks[-1] > 200:
            section = np.abs(curvatures[breaks[-1] + 1:index])
            if section.size:
                candidate = breaks[-1] + 1 + int(section.argmax())
                if candidate - breaks[-1] > 35 and candidate < index - 35 and abs(slopes[candidate]) < 0.3:
                    breaks.append(candidate)
    breaks.append(len(slopes) - 1)
    tangents = []
    for part in range(len(breaks) - 1):
        lower, upper = breaks[part], breaks[part + 1]
        candidates = extrema[(x_fit[extrema] > x_fit[lower]) & (x_fit[extrema] < x_fit[upper])]
        peak = int(candidates[np.abs(slopes[candidates]).argmax()]) if candidates.size else (lower + upper) // 2
        midpoint = (x_fit[lower] + x_fit[upper]) / 2.0
        offset = min(int(10.0 / np.sqrt(1.0 + slopes[peak] ** 2)), int(abs(x_fit[peak] - midpoint)))
        adjusted = peak + offset if x_fit[peak] > midpoint and part < len(breaks) - 2 else max(peak - offset, int((x_fit[upper] - x_fit[lower]) * 0.15))
        tolerance = int((x_fit[upper] - x_fit[lower]) * 0.15)
        mean_slope = float(np.mean(slopes[max(adjusted - tolerance, 0):adjusted + tolerance + 1]))
        vx = 1.0 / np.sqrt(1.0 + mean_slope ** 2)
        vy = mean_slope / np.sqrt(1.0 + mean_slope ** 2)
        row = float(x_fit[peak] / ratio + row_offset)
        column = float(curve(x_fit[peak]) / ratio + column_offset)
        # Keep the review handles close to the detected spine.  The upstream
        # demo used long drawing-only rays; those obscure the radiograph when
        # converted back to full-resolution DICOM coordinates.
        length = max(45.0, min(90.0, float(box[2] - box[0]) * 0.65))
        tangents.append(((column + length * -vx, row + length * vy), (column - length * -vx, row - length * vy), vx, vy))
    if len(tangents) < 2:
        raise ValueError("Omurga maskesinden iki Cobb tanjantı üretilemedi.")
    angles = []
    for first_line, second_line in zip(tangents, tangents[1:]):
        dot = np.clip(first_line[2] * second_line[2] + first_line[3] * second_line[3], -1.0, 1.0)
        angles.append(float(np.degrees(np.arccos(dot))))
    best = int(np.argmax(angles))
    points = tangents[best][0:2] + tangents[best + 1][0:2]
    clipped = []
    height, width = binary.shape
    for start, end in (points[:2], points[2:]):
        accepted, first_point, second_point = cv2.clipLine(
            (0, 0, width, height),
            (int(round(start[0])), int(round(start[1]))),
            (int(round(end[0])), int(round(end[1]))),
        )
        if not accepted:
            raise ValueError("Cobb tanjantı görüntü sınırları içinde oluşturulamadı.")
        clipped.extend((first_point, second_point))
    return angles[best], tuple((float(x), float(y)) for x, y in clipped)
