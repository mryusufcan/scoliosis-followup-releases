from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
ENGINE = ROOT / "modular_app" / "core" / "stitching_engine.py"
RESTORE = ROOT / ".restore_points"

if not MAIN.is_file():
    raise SystemExit(f"[HATA] main.py bulunamadi: {MAIN}")
if not ENGINE.is_file():
    raise SystemExit("[HATA] stitching_engine.py bulunamadi. Once Asama 1 calistirilmali.")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = RESTORE / f"stitch_engine_stage2_{stamp}"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(MAIN, backup / "main.py")
shutil.copy2(ENGINE, backup / "stitching_engine.py")

main_text = MAIN.read_text(encoding="utf-8-sig")
engine_text = ENGINE.read_text(encoding="utf-8-sig")

method_code = '\n    def compose_stitched(\n        self,\n        arrays,\n        part_keys,\n        paths,\n        junction_offsets,\n        part_offsets,\n        *,\n        render_scale=1.0,\n        gray_flags=None,\n        gray_cache=None,\n        checkerboard=False,\n    ):\n        if not arrays:\n            return None\n\n        gray_flags = gray_flags or {}\n        gray_cache = gray_cache or {}\n        render_scale = float(render_scale)\n        work_arrays = list(arrays)\n\n        if render_scale < 0.999:\n            scaled = []\n            for arr in work_arrays:\n                nh = max(1, int(round(arr.shape[0] * render_scale)))\n                nw = max(1, int(round(arr.shape[1] * render_scale)))\n                if nh == arr.shape[0] and nw == arr.shape[1]:\n                    a2 = arr\n                else:\n                    ys = np.linspace(0, arr.shape[0] - 1, nh).astype(np.int32)\n                    xs = np.linspace(0, arr.shape[1] - 1, nw).astype(np.int32)\n                    a2 = arr[np.ix_(ys, xs)]\n                scaled.append(a2)\n            work_arrays = scaled\n            junction_offsets = [\n                (dx * render_scale, dy * render_scale, score)\n                for dx, dy, score in junction_offsets\n            ]\n        else:\n            junction_offsets = list(junction_offsets)\n\n        positions = [(0.0, 0.0)]\n        curr_x = 0.0\n        curr_y = 0.0\n\n        for i in range(1, len(work_arrays)):\n            h_prev = work_arrays[i - 1].shape[0]\n            if (i - 1) < len(junction_offsets):\n                dx_auto, dy_auto, _ = junction_offsets[i - 1]\n                if dy_auto <= 0:\n                    dy_auto = h_prev * 0.20\n                dy_auto = float(np.clip(dy_auto, 1, max(1, h_prev - 1)))\n                curr_x += dx_auto\n                curr_y += h_prev - dy_auto\n            else:\n                curr_y += h_prev * 0.80\n\n            part_key = part_keys[i]\n            part_dx, part_dy = part_offsets.get(part_key, [0.0, 0.0])\n            positions.append((\n                curr_x + float(part_dx) * render_scale,\n                curr_y + float(part_dy) * render_scale,\n            ))\n\n        min_x = min(p[0] for p in positions)\n        min_y = min(p[1] for p in positions)\n        shifted_positions = [(p[0] - min_x, p[1] - min_y) for p in positions]\n\n        max_w = int(np.ceil(max(\n            p[0] + arr.shape[1]\n            for p, arr in zip(shifted_positions, work_arrays)\n        )))\n        max_h = int(np.ceil(max(\n            p[1] + arr.shape[0]\n            for p, arr in zip(shifted_positions, work_arrays)\n        )))\n        if max_w <= 0 or max_h <= 0:\n            return None\n\n        gray_fast = all(bool(gray_flags.get(path, False)) for path in paths)\n\n        if gray_fast:\n            canvas_gray = np.zeros((max_h, max_w), dtype=np.float32)\n            canvas_alpha = np.zeros((max_h, max_w), dtype=np.float32)\n\n            for i, arr in enumerate(work_arrays):\n                img_h, img_w = arr.shape[:2]\n                x = int(round(shifted_positions[i][0]))\n                y = int(round(shifted_positions[i][1]))\n\n                top_overlap = 0\n                if i > 0 and (i - 1) < len(junction_offsets):\n                    top_overlap = int(np.clip(\n                        junction_offsets[i - 1][1], 1, max(1, img_h - 1)\n                    ))\n                bottom_overlap = 0\n                if i < len(junction_offsets):\n                    bottom_overlap = int(np.clip(\n                        junction_offsets[i][1], 1, max(1, img_h - 1)\n                    ))\n\n                mask = self.get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)\n\n                dst_x1 = max(0, x)\n                dst_y1 = max(0, y)\n                dst_x2 = min(max_w, x + img_w)\n                dst_y2 = min(max_h, y + img_h)\n                if dst_x1 >= dst_x2 or dst_y1 >= dst_y2:\n                    continue\n\n                src_x1 = dst_x1 - x\n                src_y1 = dst_y1 - y\n                src_x2 = src_x1 + (dst_x2 - dst_x1)\n                src_y2 = src_y1 + (dst_y2 - dst_y1)\n\n                cache = gray_cache.get(paths[i])\n                if (\n                    render_scale >= 0.999\n                    and cache is not None\n                    and cache.shape[:2] == arr.shape[:2]\n                ):\n                    src_gray = cache[src_y1:src_y2, src_x1:src_x2]\n                else:\n                    src_gray = arr[src_y1:src_y2, src_x1:src_x2, 0].astype(np.float32)\n\n                local_mask = mask[src_y1:src_y2, src_x1:src_x2]\n                dst_gray = canvas_gray[dst_y1:dst_y2, dst_x1:dst_x2]\n                dst_alpha = canvas_alpha[dst_y1:dst_y2, dst_x1:dst_x2]\n\n                out_alpha = local_mask + dst_alpha * (1.0 - local_mask)\n                valid = out_alpha > 1e-6\n                numerator = src_gray * local_mask + dst_gray * dst_alpha * (1.0 - local_mask)\n                dst_gray[valid] = numerator[valid] / out_alpha[valid]\n                dst_gray[~valid] = 0.0\n                dst_alpha[:] = out_alpha\n\n            result_gray = np.clip(canvas_gray, 0, 255).astype(np.uint8)\n            result_arr = self.gray_to_bgra(result_gray, canvas_alpha * 255.0)\n        else:\n            canvas = np.zeros((max_h, max_w, 4), dtype=np.float32)\n\n            for i, arr in enumerate(work_arrays):\n                img_h, img_w = arr.shape[:2]\n                x = int(round(shifted_positions[i][0]))\n                y = int(round(shifted_positions[i][1]))\n\n                top_overlap = 0\n                if i > 0 and (i - 1) < len(junction_offsets):\n                    top_overlap = int(np.clip(\n                        junction_offsets[i - 1][1], 1, max(1, img_h - 1)\n                    ))\n                bottom_overlap = 0\n                if i < len(junction_offsets):\n                    bottom_overlap = int(np.clip(\n                        junction_offsets[i][1], 1, max(1, img_h - 1)\n                    ))\n\n                mask = self.get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)\n\n                dst_x1 = max(0, x)\n                dst_y1 = max(0, y)\n                dst_x2 = min(max_w, x + img_w)\n                dst_y2 = min(max_h, y + img_h)\n                if dst_x1 >= dst_x2 or dst_y1 >= dst_y2:\n                    continue\n\n                src_x1 = dst_x1 - x\n                src_y1 = dst_y1 - y\n                src_x2 = src_x1 + (dst_x2 - dst_x1)\n                src_y2 = src_y1 + (dst_y2 - dst_y1)\n\n                src = arr[src_y1:src_y2, src_x1:src_x2].astype(np.float32)\n                dst = canvas[dst_y1:dst_y2, dst_x1:dst_x2]\n                local_mask = mask[src_y1:src_y2, src_x1:src_x2]\n\n                src_alpha = local_mask[..., None] * (src[..., 3:4] / 255.0)\n                dst_alpha = dst[..., 3:4] / 255.0\n                out_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)\n                numerator = (\n                    src[..., :3] * src_alpha\n                    + dst[..., :3] * dst_alpha * (1.0 - src_alpha)\n                )\n\n                out_rgb = np.zeros_like(numerator)\n                valid = out_alpha[..., 0] > 1e-6\n                out_rgb[valid] = numerator[valid] / out_alpha[valid]\n\n                out = np.zeros_like(dst)\n                out[..., :3] = out_rgb\n                out[..., 3:4] = out_alpha * 255.0\n                canvas[dst_y1:dst_y2, dst_x1:dst_x2] = out\n\n            result_arr = np.clip(canvas, 0, 255).astype(np.uint8)\n\n        if checkerboard and junction_offsets:\n            for i in range(1, len(shifted_positions)):\n                overlap = int(max(0, min(\n                    float(junction_offsets[i - 1][1]),\n                    work_arrays[i - 1].shape[0],\n                    work_arrays[i].shape[0],\n                )))\n                if overlap > 1:\n                    y_start = int(round(shifted_positions[i][1]))\n                    result_arr = self.apply_checker_bw(\n                        result_arr,\n                        y_start,\n                        y_start + overlap,\n                        cell=22,\n                        intensity=0.32,\n                    )\n\n        return result_arr\n'
if "def compose_stitched(" not in engine_text:
    engine_text = engine_text.rstrip() + "\n" + method_code + "\n"

ast.parse(engine_text)

tree = ast.parse(main_text)
app_class = next(
    (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ScoliosisFollowUpApp"),
    None,
)
if app_class is None:
    raise RuntimeError("ScoliosisFollowUpApp sinifi bulunamadi.")

func = next(
    (node for node in app_class.body if isinstance(node, ast.FunctionDef) and node.name == "update_stitched_spine"),
    None,
)
if func is None:
    raise RuntimeError("update_stitched_spine bulunamadi.")

lines = main_text.splitlines(keepends=True)
start_idx = None
end_idx = None

for i in range(func.lineno - 1, func.end_lineno):
    line = lines[i]
    if start_idx is None and 'render_scale = float(getattr(self, "_stitch_preview_scale"' in line:
        start_idx = i
    if "result_img = self._numpy_to_qimage(result_arr)" in line:
        end_idx = i
        break

if start_idx is None or end_idx is None:
    raise RuntimeError(
        "Asama 2 render blogu bulunamadi. main.py beklenen surumden farkli; dosya degistirilmedi."
    )

replacement = '        render_scale = (\n            float(getattr(self, "_stitch_preview_scale", 1.0))\n            if getattr(self, "_stitch_interactive", False)\n            else 1.0\n        )\n\n        gray_flags_for_render = dict(self._stitch_gray_flag_cache)\n        if rotated_any:\n            gray_flags_for_render = {\n                path: False for path in gray_flags_for_render\n            }\n\n        checkerboard_on = (\n            hasattr(self, "chk_checkerboard")\n            and self.chk_checkerboard.isChecked()\n        )\n\n        result_arr = self.stitch_engine.compose_stitched(\n            arrays=arrays,\n            part_keys=valid_parts,\n            paths=[self.stitch_files[p] for p in valid_parts],\n            junction_offsets=junction_offsets,\n            part_offsets=self.stitch_part_offsets,\n            render_scale=render_scale,\n            gray_flags=gray_flags_for_render,\n            gray_cache=self._stitch_gray_cache,\n            checkerboard=checkerboard_on,\n        )\n        if result_arr is None:\n            return\n\n        result_img = self._numpy_to_qimage(result_arr)\n'
lines[start_idx:end_idx + 1] = [replacement]
new_main = "".join(lines)

ast.parse(new_main)

ENGINE.write_text(engine_text, encoding="utf-8")
MAIN.write_text(new_main, encoding="utf-8")

print()
print("=== STITCHING REFACTOR | ASAMA 2 TAMAMLANDI ===")
print(f"[YEDEK] {backup}")
print("[GUNCELLENDI] modular_app/core/stitching_engine.py")
print("[GUNCELLENDI] main.py")
print()
print("Motora tasinanlar:")
print("  - preview resize")
print("  - parca pozisyonlari")
print("  - canvas boyutu")
print("  - grayscale feather blend")
print("  - BGRA feather blend")
print("  - checkerboard overlap")
print()
print("Simdi:")
print("  python -m unittest discover -s tests")
print("  python main.py")
