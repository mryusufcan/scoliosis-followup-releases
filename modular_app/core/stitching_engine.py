from __future__ import annotations

import numpy as np


class StitchingEngine:
    """Stitching'in UI'dan bagimsiz sayisal hesaplama katmani."""

    def __init__(self, mask_cache=None):
        self.mask_cache = mask_cache if mask_cache is not None else {}

    @staticmethod
    def resize_gray_fast(gray, width, height):
        h, w = gray.shape[:2]
        if w == width and h == height:
            return gray.astype(np.float32, copy=False)
        ys = np.linspace(0, h - 1, height).astype(np.int32)
        xs = np.linspace(0, w - 1, width).astype(np.int32)
        return gray[np.ix_(ys, xs)].astype(np.float32, copy=False)

    @staticmethod
    def match_histogram_linear(arr_src, arr_ref, y_src_slice, y_ref_slice):
        src_region = arr_src[y_src_slice][..., :3].astype(np.float32)
        ref_region = arr_ref[y_ref_slice][..., :3].astype(np.float32)
        if src_region.size == 0 or ref_region.size == 0:
            return arr_src
        src_mean, src_std = src_region.mean(), src_region.std() + 1e-6
        ref_mean, ref_std = ref_region.mean(), ref_region.std() + 1e-6
        rgb = arr_src[..., :3].astype(np.float32)
        rgb = (rgb - src_mean) * (ref_std / src_std) + ref_mean
        arr_src[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        return arr_src

    @staticmethod
    def to_gray(arr_bgra):
        b = arr_bgra[..., 0].astype(np.float32)
        g = arr_bgra[..., 1].astype(np.float32)
        r = arr_bgra[..., 2].astype(np.float32)
        return 0.114 * b + 0.587 * g + 0.299 * r

    @staticmethod
    def tile_normalize(gray, tile=24):
        h, w = gray.shape
        pad_h = (-h) % tile
        pad_w = (-w) % tile
        padded = np.pad(gray, ((0, pad_h), (0, pad_w)), mode="reflect").astype(np.float32)
        ph, pw = padded.shape
        blocks = padded.reshape(ph // tile, tile, pw // tile, tile)
        means = blocks.mean(axis=(1, 3), keepdims=True)
        stds = blocks.std(axis=(1, 3), keepdims=True) + 1e-4
        normed = (blocks - means) / stds
        return normed.reshape(ph, pw)[:h, :w]

    @staticmethod
    def sobel_magnitude(gray):
        gray = gray.astype(np.float32)
        padded = np.pad(gray, 1, mode="reflect")
        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
        ky = kx.T
        gx = np.zeros_like(gray)
        gy = np.zeros_like(gray)
        for i in range(3):
            for j in range(3):
                window = padded[i:i + gray.shape[0], j:j + gray.shape[1]]
                gx += kx[i, j] * window
                gy += ky[i, j] * window
        return np.hypot(gx, gy)

    @staticmethod
    def phase_correlate(img_a, img_b):
        h, w = img_a.shape
        win = np.hanning(h)[:, None] * np.hanning(w)[None, :]
        a = (img_a - img_a.mean()) * win
        b = (img_b - img_b.mean()) * win
        fa = np.fft.fft2(a)
        fb = np.fft.fft2(b)
        r_fft = fa * np.conj(fb)
        r_fft /= np.abs(r_fft) + 1e-8
        r = np.fft.fftshift(np.fft.ifft2(r_fft).real)
        peak_idx = np.unravel_index(np.argmax(r), r.shape)
        peak_val = r[peak_idx]
        dy = peak_idx[0] - h // 2
        dx = peak_idx[1] - w // 2
        score = float(np.clip(peak_val / (np.mean(np.abs(r)) * 50 + 1e-8), 0.0, 1.0))
        return dx, dy, score

    @staticmethod
    def rotate_array(arr, angle_deg, fill=0):
        if abs(angle_deg) < 1e-6:
            return arr.copy()
        h, w = arr.shape[0], arr.shape[1]
        angle = np.radians(angle_deg)
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        cy, cx = h / 2.0, w / 2.0
        yy, xx = np.indices((h, w))
        x_rel = xx - cx
        y_rel = yy - cy
        src_x = cos_a * x_rel + sin_a * y_rel + cx
        src_y = -sin_a * x_rel + cos_a * y_rel + cy
        src_xi = np.clip(np.round(src_x).astype(np.int32), 0, w - 1)
        src_yi = np.clip(np.round(src_y).astype(np.int32), 0, h - 1)
        valid = (
            (np.round(src_x) >= 0) & (np.round(src_x) < w)
            & (np.round(src_y) >= 0) & (np.round(src_y) < h)
        )
        out = arr[src_yi, src_xi]
        mask = valid if out.ndim == 2 else valid[..., None]
        out = np.where(mask, out, fill)
        return out.astype(arr.dtype)

    @staticmethod
    def gray_to_bgra(gray, alpha=None):
        gray = np.ascontiguousarray(gray, dtype=np.uint8)
        h, w = gray.shape
        out = np.empty((h, w, 4), dtype=np.uint8)
        out[..., 0] = gray
        out[..., 1] = gray
        out[..., 2] = gray
        if alpha is None:
            out[..., 3] = 255
        else:
            out[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
        return out

    def get_stitch_mask(self, img_h, img_w, top_overlap, bottom_overlap):
        key = (int(img_h), int(img_w), int(top_overlap), int(bottom_overlap))
        cached = self.mask_cache.get(key)
        if cached is not None:
            return cached

        mask = np.ones((img_h, img_w), dtype=np.float32)
        if top_overlap > 1:
            n = min(int(top_overlap), img_h)
            if n > 1:
                ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
                ramp = ramp * ramp * (3.0 - 2.0 * ramp)
                mask[:n, :] *= ramp[:, None]
        if bottom_overlap > 1:
            n = min(int(bottom_overlap), img_h)
            if n > 1:
                ramp = np.linspace(1.0, 0.0, n, dtype=np.float32)
                ramp = ramp * ramp * (3.0 - 2.0 * ramp)
                mask[img_h - n:img_h, :] *= ramp[:, None]

        self.mask_cache[key] = mask
        return mask

    @staticmethod
    def apply_checker_bw(arr, y_start, y_end, cell=20, intensity=0.32):
        if arr is None or arr.ndim != 3 or arr.shape[2] < 4:
            return arr

        y_start = max(0, int(y_start))
        y_end = min(arr.shape[0], int(y_end))
        if y_end <= y_start:
            return arr

        w = arr.shape[1]
        band_h = y_end - y_start
        yy, xx = np.indices((band_h, w))
        checker = ((xx // max(4, int(cell))) + (yy // max(4, int(cell)))) % 2 == 0

        region = arr[y_start:y_end, :, :3].astype(np.float32)
        alpha = arr[y_start:y_end, :, 3:4].astype(np.float32)

        visible = alpha > 1.0
        bright = region * (1.0 - intensity) + 255.0 * intensity
        dark = region * (1.0 - intensity)
        mixed = np.where(checker[..., None], bright, dark)

        region_new = np.where(visible, mixed, region)
        arr[y_start:y_end, :, :3] = np.clip(region_new, 0, 255).astype(np.uint8)
        return arr


    @staticmethod
    def _cosine_ramp(n: int) -> np.ndarray:
        n = int(max(1, n))
        if n <= 1:
            return np.ones((n,), dtype=np.float32)
        t = np.linspace(0.0, 1.0, n, dtype=np.float32)
        return 0.5 - 0.5 * np.cos(np.pi * t)

    @staticmethod
    def _robust_local_match(src_gray, dst_gray, mask):
        """Estimate a conservative local gain/offset over the real overlap."""
        valid = mask.astype(bool)
        if valid.ndim != 2 or not np.any(valid):
            return 1.0, 0.0

        s = src_gray[valid].astype(np.float32)
        d = dst_gray[valid].astype(np.float32)
        if s.size < 64 or d.size < 64:
            return 1.0, 0.0

        # Robust center/spread, less sensitive than global mean/std to anatomy.
        s_med = float(np.median(s))
        d_med = float(np.median(d))
        s_p10, s_p90 = np.percentile(s, [10, 90])
        d_p10, d_p90 = np.percentile(d, [10, 90])
        s_span = max(8.0, float(s_p90 - s_p10))
        d_span = max(8.0, float(d_p90 - d_p10))

        gain = float(np.clip(d_span / s_span, 0.85, 1.18))
        offset = float(np.clip(d_med - s_med * gain, -22.0, 22.0))
        return gain, offset

    @classmethod
    def _blend_gray_overlap(cls, src_gray, dst_gray, overlap_mask, blend_h):
        """Complementary cosine feather + conservative local exposure matching."""
        if blend_h <= 1:
            return dst_gray

        h = min(int(blend_h), src_gray.shape[0], dst_gray.shape[0], overlap_mask.shape[0])
        if h <= 1:
            return dst_gray

        local_src = src_gray[:h].astype(np.float32, copy=True)
        local_dst = dst_gray[:h].astype(np.float32, copy=True)
        local_occ = overlap_mask[:h].astype(bool)

        gain, offset = cls._robust_local_match(local_src, local_dst, local_occ)
        local_src = np.clip(local_src * gain + offset, 0.0, 255.0)

        w_new = cls._cosine_ramp(h)[:, None]
        blended = local_dst * (1.0 - w_new) + local_src * w_new
        local_dst[local_occ] = blended[local_occ]
        dst_gray[:h] = local_dst
        return dst_gray

    @classmethod
    def _blend_rgb_overlap(cls, src_rgb, dst_rgb, overlap_mask, blend_h):
        """RGB equivalent of the gray complementary feather."""
        if blend_h <= 1:
            return dst_rgb

        h = min(int(blend_h), src_rgb.shape[0], dst_rgb.shape[0], overlap_mask.shape[0])
        if h <= 1:
            return dst_rgb

        local_src = src_rgb[:h].astype(np.float32, copy=True)
        local_dst = dst_rgb[:h].astype(np.float32, copy=True)
        local_occ = overlap_mask[:h].astype(bool)

        src_gray = 0.114 * local_src[..., 0] + 0.587 * local_src[..., 1] + 0.299 * local_src[..., 2]
        dst_gray = 0.114 * local_dst[..., 0] + 0.587 * local_dst[..., 1] + 0.299 * local_dst[..., 2]
        gain, offset = cls._robust_local_match(src_gray, dst_gray, local_occ)

        local_src = np.clip(local_src * gain + offset, 0.0, 255.0)
        w_new = cls._cosine_ramp(h)[:, None, None]
        blended = local_dst * (1.0 - w_new) + local_src * w_new
        local_dst[local_occ] = blended[local_occ]
        dst_rgb[:h] = local_dst
        return dst_rgb

    @staticmethod
    def _quality_score_v2(
        raw_score,
        *,
        dx,
        dy,
        upper_shape,
        lower_shape,
        overlap_edge_similarity=None,
        seam_intensity_difference=None,
    ):
        """Conservative technical score combining correlation and geometric sanity."""
        raw = float(np.clip(raw_score, 0.0, 1.0))
        h_up, w_up = upper_shape[:2]
        h_lo, w_lo = lower_shape[:2]

        # 1) Correlation component. Keep it important, but never sufficient alone.
        corr_component = raw

        # 2) Overlap sanity. Prefer a meaningful overlap band, penalize extremes.
        overlap_ratio = float(dy) / max(1.0, float(min(h_up, h_lo)))
        if 0.12 <= overlap_ratio <= 0.32:
            overlap_component = 1.0
        elif 0.08 <= overlap_ratio < 0.12 or 0.32 < overlap_ratio <= 0.40:
            overlap_component = 0.72
        else:
            overlap_component = 0.35

        # 3) Horizontal translation sanity.
        width_ref = max(1.0, float(min(w_up, w_lo)))
        dx_ratio = abs(float(dx)) / width_ref
        if dx_ratio <= 0.03:
            shift_component = 1.0
        elif dx_ratio <= 0.08:
            shift_component = 0.78
        elif dx_ratio <= 0.15:
            shift_component = 0.55
        else:
            shift_component = 0.25

        # 4) Post-alignment edge similarity, if available.
        if overlap_edge_similarity is None:
            edge_component = 0.65
        else:
            edge_component = float(np.clip(overlap_edge_similarity, 0.0, 1.0))

        # 5) Seam intensity continuity. Convert mean absolute difference to 0..1.
        if seam_intensity_difference is None:
            seam_component = 0.65
        else:
            diff = max(0.0, float(seam_intensity_difference))
            seam_component = float(np.clip(1.0 - diff / 55.0, 0.0, 1.0))

        # Weighted blend. A perfect phase peak alone can therefore no longer
        # produce an automatic 1.00 quality score.
        score = (
            0.42 * corr_component
            + 0.18 * overlap_component
            + 0.12 * shift_component
            + 0.18 * edge_component
            + 0.10 * seam_component
        )
        return float(np.clip(score, 0.0, 1.0))

    @classmethod
    def evaluate_junction_quality(
        cls,
        upper_arr,
        lower_arr,
        dx,
        dy,
        raw_score,
    ):
        """Evaluate one junction after alignment using edge and intensity continuity."""
        try:
            h_up, w_up = upper_arr.shape[:2]
            h_lo, w_lo = lower_arr.shape[:2]
            overlap = int(round(float(dy)))

            if overlap <= 4:
                return cls._quality_score_v2(
                    raw_score,
                    dx=dx,
                    dy=dy,
                    upper_shape=upper_arr.shape,
                    lower_shape=lower_arr.shape,
                ), None, None

            overlap = min(overlap, h_up, h_lo)
            band_w = min(w_up, w_lo)

            # Apply horizontal shift as a simple common visible crop.
            shift = int(round(float(dx)))
            if shift >= 0:
                up_x1 = shift
                lo_x1 = 0
            else:
                up_x1 = 0
                lo_x1 = -shift

            usable_w = min(w_up - up_x1, w_lo - lo_x1, band_w)
            if usable_w < 32:
                return cls._quality_score_v2(
                    raw_score,
                    dx=dx,
                    dy=dy,
                    upper_shape=upper_arr.shape,
                    lower_shape=lower_arr.shape,
                ), None, None

            upper_band = upper_arr[h_up - overlap:h_up, up_x1:up_x1 + usable_w]
            lower_band = lower_arr[:overlap, lo_x1:lo_x1 + usable_w]

            upper_gray = cls.to_gray(upper_band).astype(np.float32)
            lower_gray = cls.to_gray(lower_band).astype(np.float32)

            # Compare central overlap, avoiding detector edges.
            y_margin = max(2, int(overlap * 0.12))
            x_margin = max(4, int(usable_w * 0.05))
            y1 = y_margin
            y2 = max(y1 + 1, overlap - y_margin)
            x1 = x_margin
            x2 = max(x1 + 1, usable_w - x_margin)

            ug = upper_gray[y1:y2, x1:x2]
            lg = lower_gray[y1:y2, x1:x2]
            if ug.size < 128 or lg.size < 128:
                edge_similarity = None
                intensity_diff = None
            else:
                # Robust exposure normalization before edge comparison.
                def normalize(g):
                    med = np.median(g)
                    p10, p90 = np.percentile(g, [10, 90])
                    scale = max(8.0, float(p90 - p10))
                    return (g - med) / scale

                un = normalize(ug)
                ln = normalize(lg)

                ue = cls.sobel_magnitude(un)
                le = cls.sobel_magnitude(ln)

                ue = ue.ravel()
                le = le.ravel()
                ue -= ue.mean()
                le -= le.mean()
                denom = float(np.linalg.norm(ue) * np.linalg.norm(le))
                if denom > 1e-6:
                    corr = float(np.dot(ue, le) / denom)
                    edge_similarity = float(np.clip((corr + 1.0) * 0.5, 0.0, 1.0))
                else:
                    edge_similarity = 0.0

                # Exposure difference after conservative local matching.
                gain, offset = cls._robust_local_match(
                    lower_gray, upper_gray, np.ones_like(lower_gray, dtype=bool)
                )
                lower_matched = np.clip(lower_gray * gain + offset, 0.0, 255.0)
                intensity_diff = float(np.mean(np.abs(
                    upper_gray[y1:y2, x1:x2] - lower_matched[y1:y2, x1:x2]
                )))

            final_score = cls._quality_score_v2(
                raw_score,
                dx=dx,
                dy=dy,
                upper_shape=upper_arr.shape,
                lower_shape=lower_arr.shape,
                overlap_edge_similarity=edge_similarity,
                seam_intensity_difference=intensity_diff,
            )
            return final_score, edge_similarity, intensity_diff

        except Exception:
            final_score = cls._quality_score_v2(
                raw_score,
                dx=dx,
                dy=dy,
                upper_shape=upper_arr.shape,
                lower_shape=lower_arr.shape,
            )
            return final_score, None, None

    @staticmethod
    def assess_alignment_quality(junction_offsets, *, min_score=0.18, warn_score=0.32):
        """Return a non-diagnostic technical quality summary for stitch alignment."""
        if not junction_offsets:
            return {
                "status": "unknown",
                "average_score": None,
                "minimum_score": None,
                "poor_count": 0,
                "warning_count": 0,
                "junctions": [],
            }

        junctions = []
        for index, item in enumerate(junction_offsets):
            if isinstance(item, dict):
                dx = float(item.get("dx", 0.0))
                dy = float(item.get("dy", 0.0))
                score = float(item.get("score", 0.0))
                raw_score = item.get("raw_score")
                edge_similarity = item.get("edge_similarity")
                seam_intensity_difference = item.get("seam_intensity_difference")
            else:
                dx, dy, score = item[:3]
                dx = float(dx)
                dy = float(dy)
                score = float(score)
                raw_score = None
                edge_similarity = None
                seam_intensity_difference = None
            if score < float(min_score):
                status = "poor"
            elif score < float(warn_score):
                status = "warning"
            else:
                status = "good"
            junctions.append({
                "index": index,
                "dx": float(dx),
                "dy": float(dy),
                "score": score,
                "raw_score": raw_score,
                "edge_similarity": edge_similarity,
                "seam_intensity_difference": seam_intensity_difference,
                "status": status,
            })

        scores = [row["score"] for row in junctions]
        minimum = min(scores)
        average = sum(scores) / len(scores)
        poor = sum(1 for row in junctions if row["status"] == "poor")
        warn = sum(1 for row in junctions if row["status"] == "warning")

        if poor:
            status = "poor"
        elif warn:
            status = "warning"
        else:
            status = "good"

        return {
            "status": status,
            "average_score": average,
            "minimum_score": minimum,
            "poor_count": poor,
            "warning_count": warn,
            "junctions": junctions,
        }

    def compose_stitched(
        self,
        arrays,
        part_keys,
        paths,
        junction_offsets,
        part_offsets,
        *,
        render_scale=1.0,
        gray_flags=None,
        gray_cache=None,
        checkerboard=False,
    ):
        if not arrays:
            return None

        gray_flags = gray_flags or {}
        gray_cache = gray_cache or {}
        render_scale = float(render_scale)
        work_arrays = list(arrays)

        if render_scale < 0.999:
            scaled = []
            for arr in work_arrays:
                nh = max(1, int(round(arr.shape[0] * render_scale)))
                nw = max(1, int(round(arr.shape[1] * render_scale)))
                if nh == arr.shape[0] and nw == arr.shape[1]:
                    a2 = arr
                else:
                    ys = np.linspace(0, arr.shape[0] - 1, nh).astype(np.int32)
                    xs = np.linspace(0, arr.shape[1] - 1, nw).astype(np.int32)
                    a2 = arr[np.ix_(ys, xs)]
                scaled.append(a2)
            work_arrays = scaled
            junction_offsets = [
                (dx * render_scale, dy * render_scale, score)
                for dx, dy, score in junction_offsets
            ]
        else:
            junction_offsets = list(junction_offsets)

        positions = [(0.0, 0.0)]
        curr_x = 0.0
        curr_y = 0.0

        for i in range(1, len(work_arrays)):
            h_prev = work_arrays[i - 1].shape[0]
            if (i - 1) < len(junction_offsets):
                dx_auto, dy_auto, _ = junction_offsets[i - 1]
                if dy_auto <= 0:
                    dy_auto = h_prev * 0.20
                dy_auto = float(np.clip(dy_auto, 1, max(1, h_prev - 1)))
                curr_x += dx_auto
                curr_y += h_prev - dy_auto
            else:
                curr_y += h_prev * 0.80

            part_key = part_keys[i]
            part_dx, part_dy = part_offsets.get(part_key, [0.0, 0.0])
            positions.append((
                curr_x + float(part_dx) * render_scale,
                curr_y + float(part_dy) * render_scale,
            ))

        min_x = min(p[0] for p in positions)
        min_y = min(p[1] for p in positions)
        shifted_positions = [(p[0] - min_x, p[1] - min_y) for p in positions]

        max_w = int(np.ceil(max(
            p[0] + arr.shape[1]
            for p, arr in zip(shifted_positions, work_arrays)
        )))
        max_h = int(np.ceil(max(
            p[1] + arr.shape[0]
            for p, arr in zip(shifted_positions, work_arrays)
        )))
        if max_w <= 0 or max_h <= 0:
            return None

        gray_fast = all(bool(gray_flags.get(path, False)) for path in paths)

        if gray_fast:
            canvas_gray = np.zeros((max_h, max_w), dtype=np.float32)
            canvas_alpha = np.zeros((max_h, max_w), dtype=np.float32)

            for i, arr in enumerate(work_arrays):
                img_h, img_w = arr.shape[:2]
                x = int(round(shifted_positions[i][0]))
                y = int(round(shifted_positions[i][1]))

                top_overlap = 0
                if i > 0 and (i - 1) < len(junction_offsets):
                    top_overlap = int(np.clip(
                        junction_offsets[i - 1][1], 1, max(1, img_h - 1)
                    ))
                bottom_overlap = 0
                if i < len(junction_offsets):
                    bottom_overlap = int(np.clip(
                        junction_offsets[i][1], 1, max(1, img_h - 1)
                    ))

                mask = self.get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)

                dst_x1 = max(0, x)
                dst_y1 = max(0, y)
                dst_x2 = min(max_w, x + img_w)
                dst_y2 = min(max_h, y + img_h)
                if dst_x1 >= dst_x2 or dst_y1 >= dst_y2:
                    continue

                src_x1 = dst_x1 - x
                src_y1 = dst_y1 - y
                src_x2 = src_x1 + (dst_x2 - dst_x1)
                src_y2 = src_y1 + (dst_y2 - dst_y1)

                cache = gray_cache.get(paths[i])
                if (
                    render_scale >= 0.999
                    and cache is not None
                    and cache.shape[:2] == arr.shape[:2]
                ):
                    src_gray = cache[src_y1:src_y2, src_x1:src_x2]
                else:
                    src_gray = arr[src_y1:src_y2, src_x1:src_x2, 0].astype(np.float32)

                local_mask = mask[src_y1:src_y2, src_x1:src_x2]
                dst_gray = canvas_gray[dst_y1:dst_y2, dst_x1:dst_x2]
                dst_alpha = canvas_alpha[dst_y1:dst_y2, dst_x1:dst_x2]

                # IMPORTANT: Preserve the actual feather weights. Stage 4.1
                # converted every non-zero mask pixel to alpha=1, which discarded
                # the bottom ramp of the upper image and could leave a hard
                # horizontal detector-edge line at the junction.
                src_weight = np.clip(local_mask.astype(np.float32), 0.0, 1.0)
                dst_weight = np.clip(dst_alpha.astype(np.float32), 0.0, 1.0)

                src_visible = src_weight > 1e-6
                dst_visible = dst_weight > 1e-6
                overlap = src_visible & dst_visible

                src_adjusted = src_gray.astype(np.float32, copy=True)
                if i > 0 and np.any(overlap):
                    gain, offset = self._robust_local_match(
                        src_adjusted, dst_gray, overlap
                    )
                    src_adjusted = np.clip(
                        src_adjusted * gain + offset, 0.0, 255.0
                    )

                # Symmetric weighted average. When the upper bottom-ramp and
                # lower top-ramp overlap, their weights are complementary and
                # sum to ~1, so neither image stays artificially dominant.
                total_weight = dst_weight + src_weight
                valid = total_weight > 1e-6
                numerator = (
                    dst_gray * dst_weight
                    + src_adjusted * src_weight
                )
                dst_gray[valid] = numerator[valid] / total_weight[valid]
                dst_gray[~valid] = 0.0

                # Keep a coverage weight for the next part rather than forcing
                # alpha to 1 at the feather edge.
                dst_alpha[:] = np.clip(total_weight, 0.0, 1.0)

            result_gray = np.clip(canvas_gray, 0, 255).astype(np.uint8)
            result_arr = self.gray_to_bgra(result_gray, canvas_alpha * 255.0)
        else:
            canvas = np.zeros((max_h, max_w, 4), dtype=np.float32)

            for i, arr in enumerate(work_arrays):
                img_h, img_w = arr.shape[:2]
                x = int(round(shifted_positions[i][0]))
                y = int(round(shifted_positions[i][1]))

                top_overlap = 0
                if i > 0 and (i - 1) < len(junction_offsets):
                    top_overlap = int(np.clip(
                        junction_offsets[i - 1][1], 1, max(1, img_h - 1)
                    ))
                bottom_overlap = 0
                if i < len(junction_offsets):
                    bottom_overlap = int(np.clip(
                        junction_offsets[i][1], 1, max(1, img_h - 1)
                    ))

                mask = self.get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)

                dst_x1 = max(0, x)
                dst_y1 = max(0, y)
                dst_x2 = min(max_w, x + img_w)
                dst_y2 = min(max_h, y + img_h)
                if dst_x1 >= dst_x2 or dst_y1 >= dst_y2:
                    continue

                src_x1 = dst_x1 - x
                src_y1 = dst_y1 - y
                src_x2 = src_x1 + (dst_x2 - dst_x1)
                src_y2 = src_y1 + (dst_y2 - dst_y1)

                src = arr[src_y1:src_y2, src_x1:src_x2].astype(np.float32)
                dst = canvas[dst_y1:dst_y2, dst_x1:dst_x2]
                local_mask = mask[src_y1:src_y2, src_x1:src_x2]

                src_native_alpha = np.clip(src[..., 3] / 255.0, 0.0, 1.0)
                src_weight = np.clip(local_mask, 0.0, 1.0) * src_native_alpha
                dst_weight = np.clip(dst[..., 3] / 255.0, 0.0, 1.0)

                src_visible = src_weight > 1e-6
                dst_visible = dst_weight > 1e-6
                overlap = src_visible & dst_visible

                src_rgb = src[..., :3].astype(np.float32, copy=True)
                dst_rgb = dst[..., :3]

                if i > 0 and np.any(overlap):
                    src_gray_local = (
                        0.114 * src_rgb[..., 0]
                        + 0.587 * src_rgb[..., 1]
                        + 0.299 * src_rgb[..., 2]
                    )
                    dst_gray_local = (
                        0.114 * dst_rgb[..., 0]
                        + 0.587 * dst_rgb[..., 1]
                        + 0.299 * dst_rgb[..., 2]
                    )
                    gain, offset = self._robust_local_match(
                        src_gray_local, dst_gray_local, overlap
                    )
                    src_rgb = np.clip(src_rgb * gain + offset, 0.0, 255.0)

                total_weight = dst_weight + src_weight
                valid = total_weight > 1e-6

                numerator = (
                    dst_rgb * dst_weight[..., None]
                    + src_rgb * src_weight[..., None]
                )
                dst_rgb[valid] = (
                    numerator[valid] / total_weight[valid, None]
                )
                dst_rgb[~valid] = 0.0
                dst[..., 3] = np.clip(total_weight, 0.0, 1.0) * 255.0

            result_arr = np.clip(canvas, 0, 255).astype(np.uint8)

        if checkerboard and junction_offsets:
            for i in range(1, len(shifted_positions)):
                overlap = int(max(0, min(
                    float(junction_offsets[i - 1][1]),
                    work_arrays[i - 1].shape[0],
                    work_arrays[i].shape[0],
                )))
                if overlap > 1:
                    y_start = int(round(shifted_positions[i][1]))
                    result_arr = self.apply_checker_bw(
                        result_arr,
                        y_start,
                        y_start + overlap,
                        cell=22,
                        intensity=0.32,
                    )

        return result_arr

    def auto_estimate_offset(
        self,
        arr_top,
        arr_bottom,
        min_ratio=0.12,
        max_ratio=0.32,
        max_dx=50,
        cv=None,
    ):
        try:
            h_top, w_top = arr_top.shape[:2]
            h_bot, w_bot = arr_bottom.shape[:2]
            band_w = min(w_top, w_bot)

            min_overlap = int(h_top * min_ratio)
            max_overlap = int(h_top * max_ratio)

            if h_top < 10 or h_bot < 10 or max_overlap <= min_overlap:
                return 0.0, float(max(1, int(h_top * 0.20))), 0.0, arr_bottom

            window_h = min(120, h_top, h_bot)
            max_feature_w = 640
            scale = min(1.0, max_feature_w / float(max(1, band_w)))
            feat_w = max(64, int(round(band_w * scale)))
            feat_h = max(32, int(round(window_h * scale)))

            def make_feature(region):
                gray = self.to_gray(region).astype(np.float32)

                if cv is not None:
                    gray = cv.resize(gray, (feat_w, feat_h), interpolation=cv.INTER_AREA)
                    gray = cv.GaussianBlur(gray, (3, 3), 0)
                    gx = cv.Sobel(gray, cv.CV_32F, 1, 0, ksize=3)
                    gy = cv.Sobel(gray, cv.CV_32F, 0, 1, ksize=3)
                    feat = cv.magnitude(gx, gy)
                else:
                    gray = self.resize_gray_fast(gray, feat_w, feat_h)
                    feat = self.sobel_magnitude(gray)

                feat -= feat.mean()
                std = feat.std()
                if std > 1e-6:
                    feat /= std
                return feat.astype(np.float32)

            top_region = arr_top[max(0, h_top - window_h):h_top, :band_w]
            top_feat = make_feature(top_region)

            win = np.hanning(feat_h)[:, None] * np.hanning(feat_w)[None, :]
            top_win = top_feat * win
            top_fft = np.fft.fft2(top_win)

            best_score = -1.0
            best_dy = int(h_top * 0.20)
            best_dx = 0

            for trial_overlap in range(min_overlap, max_overlap + 1, 5):
                if trial_overlap < window_h or trial_overlap > h_bot:
                    continue

                y2 = trial_overlap
                y1 = y2 - window_h
                bot_region = arr_bottom[y1:y2, :band_w]

                if bot_region.shape[0] != window_h:
                    continue

                bot_feat = make_feature(bot_region)
                bot_win = bot_feat * win
                bot_fft = np.fft.fft2(bot_win)

                r_fft = top_fft * np.conj(bot_fft)
                r_fft /= np.abs(r_fft) + 1e-8
                corr = np.fft.fftshift(np.fft.ifft2(r_fft).real)

                peak_idx = np.unravel_index(np.argmax(corr), corr.shape)
                peak_val = float(corr[peak_idx])
                mean_abs = float(np.mean(np.abs(corr))) + 1e-8
                score = float(np.clip(
                    peak_val / (mean_abs * 50.0),
                    0.0,
                    1.0,
                ))

                dy_feat = peak_idx[0] - feat_h // 2
                dx_feat = peak_idx[1] - feat_w // 2

                dy = int(round(dy_feat / scale))
                dx = int(round(dx_feat / scale))
                calc_dy = trial_overlap + dy

                if score > best_score and min_overlap <= calc_dy <= max_overlap:
                    best_score = score
                    best_dy = calc_dy
                    best_dx = dx

            best_dx = float(np.clip(best_dx, -max_dx, max_dx))
            best_dy = float(np.clip(best_dy, min_overlap, max_overlap))
            return best_dx, best_dy, best_score, arr_bottom

        except Exception as exc:
            print(f"Dinamik cakisma hizalamasi basarisiz: {exc}")
            fallback_dy = float(int(arr_top.shape[0] * 0.20))
            return 0.0, fallback_dy, 0.0, arr_bottom

