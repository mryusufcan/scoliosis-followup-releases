from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class ManualAlignmentResult:
    dx: float
    target_y: float
    angle_deg: float
    dy_adjust: float


class StitchController:
    """Stitching durum/geometri kararlarini UI'dan ayiran katman."""

    def __init__(self, engine):
        self.engine = engine
        self.manual_stage_index = 0
        self.manual_points = {}
        self.manual_junction_offsets = {}

    @staticmethod
    def calculate_manual_alignment(
        fixed_points,
        moving_points,
        *,
        moving_width,
        moving_height,
        top_height,
        overlap_px,
        max_angle_deg=12.0,
        min_point_distance=3.0,
    ):
        """2+2 anatomik noktadan rigid manuel hizalama hesaplar.

        fixed_points: sabit goruntudeki iki nokta
        moving_points: hareketli goruntudeki ayni iki anatomik nokta
        """
        if len(fixed_points) < 2 or len(moving_points) < 2:
            raise ValueError("2+2 nokta gerekli.")

        p0 = np.asarray(fixed_points[0], dtype=np.float64)
        p1 = np.asarray(fixed_points[1], dtype=np.float64)
        q0 = np.asarray(moving_points[0], dtype=np.float64)
        q1 = np.asarray(moving_points[1], dtype=np.float64)

        v_src = q1 - q0
        v_dst = p1 - p0

        src_len = float(np.linalg.norm(v_src))
        dst_len = float(np.linalg.norm(v_dst))

        if src_len < float(min_point_distance) or dst_len < float(min_point_distance):
            raise ValueError("POINTS_TOO_CLOSE")

        angle_src = math.atan2(v_src[1], v_src[0])
        angle_dst = math.atan2(v_dst[1], v_dst[0])
        angle_deg = math.degrees(angle_dst - angle_src)
        angle_deg = float(np.clip(angle_deg, -max_angle_deg, max_angle_deg))

        cx = float(moving_width) / 2.0
        cy = float(moving_height) / 2.0

        a = math.radians(angle_deg)
        ca = math.cos(a)
        sa = math.sin(a)

        q0r_x = ca * (q0[0] - cx) - sa * (q0[1] - cy) + cx
        q0r_y = sa * (q0[0] - cx) + ca * (q0[1] - cy) + cy

        target_x = float(p0[0] - q0r_x)
        target_y = float(p0[1] - q0r_y)

        dy_adjust = target_y - (float(top_height) - float(overlap_px))

        return ManualAlignmentResult(
            dx=float(target_x),
            target_y=float(target_y),
            angle_deg=float(angle_deg),
            dy_adjust=float(dy_adjust),
        )

    @staticmethod
    def active_pairs(stitch_files):
        order = ("servical", "dorsal", "lumbar", "extra")
        active = [part for part in order if stitch_files.get(part)]
        return list(zip(active[:-1], active[1:]))

    @staticmethod
    def fresh_manual_state():
        return {
            "stage_index": 0,
            "points": {},
            "junction_offsets": {},
        }

    @staticmethod
    def reset_points_state():
        return {
            "stage_index": 0,
            "points": {},
        }

    @staticmethod
    def remove_part_from_junction_offsets(junction_offsets, part_name):
        return {
            key: value
            for key, value in junction_offsets.items()
            if part_name not in key
        }

    @staticmethod
    def can_advance_stage(stage_index, pairs, manual_points):
        if not pairs or stage_index >= len(pairs):
            return False
        return (
            len(manual_points.get(0, [])) >= 2
            and len(manual_points.get(1, [])) >= 2
        )

    @staticmethod
    def next_stage_index(stage_index, pairs):
        candidate = int(stage_index) + 1
        if candidate < len(pairs):
            return candidate
        return None

