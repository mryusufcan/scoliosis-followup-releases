from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
CORE_DIR = ROOT / "modular_app" / "core"
ENGINE = CORE_DIR / "stitching_engine.py"
INIT = CORE_DIR / "__init__.py"
RESTORE = ROOT / ".restore_points"

if not MAIN.is_file():
    raise SystemExit(f"[HATA] main.py bulunamadi: {MAIN}")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = RESTORE / f"stitch_engine_stage1_{stamp}"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(MAIN, backup / "main.py")

CORE_DIR.mkdir(parents=True, exist_ok=True)
if not INIT.exists():
    INIT.write_text('"""Goruntuleme ve hesaplama cekirdekleri."""\n', encoding="utf-8")

ENGINE.write_text('from __future__ import annotations\n\nimport numpy as np\n\n\nclass StitchingEngine:\n    """Stitching\'in UI\'dan bagimsiz sayisal hesaplama katmani."""\n\n    def __init__(self, mask_cache=None):\n        self.mask_cache = mask_cache if mask_cache is not None else {}\n\n    @staticmethod\n    def resize_gray_fast(gray, width, height):\n        h, w = gray.shape[:2]\n        if w == width and h == height:\n            return gray.astype(np.float32, copy=False)\n        ys = np.linspace(0, h - 1, height).astype(np.int32)\n        xs = np.linspace(0, w - 1, width).astype(np.int32)\n        return gray[np.ix_(ys, xs)].astype(np.float32, copy=False)\n\n    @staticmethod\n    def match_histogram_linear(arr_src, arr_ref, y_src_slice, y_ref_slice):\n        src_region = arr_src[y_src_slice][..., :3].astype(np.float32)\n        ref_region = arr_ref[y_ref_slice][..., :3].astype(np.float32)\n        if src_region.size == 0 or ref_region.size == 0:\n            return arr_src\n        src_mean, src_std = src_region.mean(), src_region.std() + 1e-6\n        ref_mean, ref_std = ref_region.mean(), ref_region.std() + 1e-6\n        rgb = arr_src[..., :3].astype(np.float32)\n        rgb = (rgb - src_mean) * (ref_std / src_std) + ref_mean\n        arr_src[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)\n        return arr_src\n\n    @staticmethod\n    def to_gray(arr_bgra):\n        b = arr_bgra[..., 0].astype(np.float32)\n        g = arr_bgra[..., 1].astype(np.float32)\n        r = arr_bgra[..., 2].astype(np.float32)\n        return 0.114 * b + 0.587 * g + 0.299 * r\n\n    @staticmethod\n    def tile_normalize(gray, tile=24):\n        h, w = gray.shape\n        pad_h = (-h) % tile\n        pad_w = (-w) % tile\n        padded = np.pad(gray, ((0, pad_h), (0, pad_w)), mode="reflect").astype(np.float32)\n        ph, pw = padded.shape\n        blocks = padded.reshape(ph // tile, tile, pw // tile, tile)\n        means = blocks.mean(axis=(1, 3), keepdims=True)\n        stds = blocks.std(axis=(1, 3), keepdims=True) + 1e-4\n        normed = (blocks - means) / stds\n        return normed.reshape(ph, pw)[:h, :w]\n\n    @staticmethod\n    def sobel_magnitude(gray):\n        gray = gray.astype(np.float32)\n        padded = np.pad(gray, 1, mode="reflect")\n        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)\n        ky = kx.T\n        gx = np.zeros_like(gray)\n        gy = np.zeros_like(gray)\n        for i in range(3):\n            for j in range(3):\n                window = padded[i:i + gray.shape[0], j:j + gray.shape[1]]\n                gx += kx[i, j] * window\n                gy += ky[i, j] * window\n        return np.hypot(gx, gy)\n\n    @staticmethod\n    def phase_correlate(img_a, img_b):\n        h, w = img_a.shape\n        win = np.hanning(h)[:, None] * np.hanning(w)[None, :]\n        a = (img_a - img_a.mean()) * win\n        b = (img_b - img_b.mean()) * win\n        fa = np.fft.fft2(a)\n        fb = np.fft.fft2(b)\n        r_fft = fa * np.conj(fb)\n        r_fft /= np.abs(r_fft) + 1e-8\n        r = np.fft.fftshift(np.fft.ifft2(r_fft).real)\n        peak_idx = np.unravel_index(np.argmax(r), r.shape)\n        peak_val = r[peak_idx]\n        dy = peak_idx[0] - h // 2\n        dx = peak_idx[1] - w // 2\n        score = float(np.clip(peak_val / (np.mean(np.abs(r)) * 50 + 1e-8), 0.0, 1.0))\n        return dx, dy, score\n\n    @staticmethod\n    def rotate_array(arr, angle_deg, fill=0):\n        if abs(angle_deg) < 1e-6:\n            return arr.copy()\n        h, w = arr.shape[0], arr.shape[1]\n        angle = np.radians(angle_deg)\n        cos_a, sin_a = np.cos(angle), np.sin(angle)\n        cy, cx = h / 2.0, w / 2.0\n        yy, xx = np.indices((h, w))\n        x_rel = xx - cx\n        y_rel = yy - cy\n        src_x = cos_a * x_rel + sin_a * y_rel + cx\n        src_y = -sin_a * x_rel + cos_a * y_rel + cy\n        src_xi = np.clip(np.round(src_x).astype(np.int32), 0, w - 1)\n        src_yi = np.clip(np.round(src_y).astype(np.int32), 0, h - 1)\n        valid = (\n            (np.round(src_x) >= 0) & (np.round(src_x) < w)\n            & (np.round(src_y) >= 0) & (np.round(src_y) < h)\n        )\n        out = arr[src_yi, src_xi]\n        mask = valid if out.ndim == 2 else valid[..., None]\n        out = np.where(mask, out, fill)\n        return out.astype(arr.dtype)\n\n    @staticmethod\n    def gray_to_bgra(gray, alpha=None):\n        gray = np.ascontiguousarray(gray, dtype=np.uint8)\n        h, w = gray.shape\n        out = np.empty((h, w, 4), dtype=np.uint8)\n        out[..., 0] = gray\n        out[..., 1] = gray\n        out[..., 2] = gray\n        if alpha is None:\n            out[..., 3] = 255\n        else:\n            out[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)\n        return out\n\n    def get_stitch_mask(self, img_h, img_w, top_overlap, bottom_overlap):\n        key = (int(img_h), int(img_w), int(top_overlap), int(bottom_overlap))\n        cached = self.mask_cache.get(key)\n        if cached is not None:\n            return cached\n\n        mask = np.ones((img_h, img_w), dtype=np.float32)\n        if top_overlap > 1:\n            n = min(int(top_overlap), img_h)\n            if n > 1:\n                ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)\n                ramp = ramp * ramp * (3.0 - 2.0 * ramp)\n                mask[:n, :] *= ramp[:, None]\n        if bottom_overlap > 1:\n            n = min(int(bottom_overlap), img_h)\n            if n > 1:\n                ramp = np.linspace(1.0, 0.0, n, dtype=np.float32)\n                ramp = ramp * ramp * (3.0 - 2.0 * ramp)\n                mask[img_h - n:img_h, :] *= ramp[:, None]\n\n        self.mask_cache[key] = mask\n        return mask\n\n    @staticmethod\n    def apply_checker_bw(arr, y_start, y_end, cell=20, intensity=0.32):\n        if arr is None or arr.ndim != 3 or arr.shape[2] < 4:\n            return arr\n\n        y_start = max(0, int(y_start))\n        y_end = min(arr.shape[0], int(y_end))\n        if y_end <= y_start:\n            return arr\n\n        w = arr.shape[1]\n        band_h = y_end - y_start\n        yy, xx = np.indices((band_h, w))\n        checker = ((xx // max(4, int(cell))) + (yy // max(4, int(cell)))) % 2 == 0\n\n        region = arr[y_start:y_end, :, :3].astype(np.float32)\n        alpha = arr[y_start:y_end, :, 3:4].astype(np.float32)\n\n        visible = alpha > 1.0\n        bright = region * (1.0 - intensity) + 255.0 * intensity\n        dark = region * (1.0 - intensity)\n        mixed = np.where(checker[..., None], bright, dark)\n\n        region_new = np.where(visible, mixed, region)\n        arr[y_start:y_end, :, :3] = np.clip(region_new, 0, 255).astype(np.uint8)\n        return arr\n', encoding="utf-8")

text = MAIN.read_text(encoding="utf-8-sig")
lines = text.splitlines(keepends=True)
tree = ast.parse(text)

app_class = next(
    (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ScoliosisFollowUpApp"),
    None,
)
if app_class is None:
    raise RuntimeError("ScoliosisFollowUpApp sinifi bulunamadi.")

method_map = {'_resize_gray_fast': '    @staticmethod\n    def _resize_gray_fast(gray, width, height):\n        return StitchingEngine.resize_gray_fast(gray, width, height)\n', '_match_histogram_linear': '    @staticmethod\n    def _match_histogram_linear(arr_src, arr_ref, y_src_slice, y_ref_slice):\n        return StitchingEngine.match_histogram_linear(arr_src, arr_ref, y_src_slice, y_ref_slice)\n', '_to_gray': '    @staticmethod\n    def _to_gray(arr_bgra):\n        return StitchingEngine.to_gray(arr_bgra)\n', '_tile_normalize': '    @staticmethod\n    def _tile_normalize(gray, tile=24):\n        return StitchingEngine.tile_normalize(gray, tile)\n', '_sobel_magnitude': '    @staticmethod\n    def _sobel_magnitude(gray):\n        return StitchingEngine.sobel_magnitude(gray)\n', '_phase_correlate': '    @staticmethod\n    def _phase_correlate(img_a, img_b):\n        return StitchingEngine.phase_correlate(img_a, img_b)\n', '_rotate_array': '    @staticmethod\n    def _rotate_array(arr, angle_deg, fill=0):\n        return StitchingEngine.rotate_array(arr, angle_deg, fill)\n', '_gray_to_bgra': '    @staticmethod\n    def _gray_to_bgra(gray, alpha=None):\n        return StitchingEngine.gray_to_bgra(gray, alpha)\n', '_get_stitch_mask': '    def _get_stitch_mask(self, img_h, img_w, top_overlap, bottom_overlap):\n        return self.stitch_engine.get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)\n', '_apply_checker_bw': '    @staticmethod\n    def _apply_checker_bw(arr, y_start, y_end, cell=20, intensity=0.32):\n        return StitchingEngine.apply_checker_bw(arr, y_start, y_end, cell, intensity)\n'}
found = {}
for node in app_class.body:
    if isinstance(node, ast.FunctionDef) and node.name in method_map:
        start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
        end = node.end_lineno
        found[node.name] = (start, end)

missing = sorted(set(method_map) - set(found))
if missing:
    raise RuntimeError(
        "Beklenen stitching helper fonksiyonlari bulunamadi: " + ", ".join(missing)
        + "\nmain.py bekledigimiz surumden farkli olabilir; main.py degistirilmedi."
    )

for name, (start, end) in sorted(found.items(), key=lambda x: x[1][0], reverse=True):
    replacement = method_map[name]
    if not replacement.endswith("\n"):
        replacement += "\n"
    lines[start:end] = [replacement]

new_text = "".join(lines)

import_line = "from modular_app.core.stitching_engine import StitchingEngine\n"
if import_line not in new_text:
    class_pos = new_text.find("\nclass ")
    if class_pos == -1:
        raise RuntimeError("StitchingEngine import noktasi bulunamadi.")
    new_text = new_text[:class_pos] + "\n" + import_line + new_text[class_pos:]

engine_init = "        self.stitch_engine = StitchingEngine(mask_cache=self._stitch_mask_cache)\n"
if engine_init not in new_text:
    cache_line = "        self._stitch_mask_cache = {}\n"
    if cache_line not in new_text:
        raise RuntimeError("_stitch_mask_cache baslatma satiri bulunamadi.")
    new_text = new_text.replace(cache_line, cache_line + engine_init, 1)

ast.parse(new_text)
MAIN.write_text(new_text, encoding="utf-8")

print()
print("=== STITCHING REFACTOR | ASAMA 1 TAMAMLANDI ===")
print(f"[YEDEK] {backup}")
print("[OLUSTU] modular_app/core/__init__.py")
print("[OLUSTU] modular_app/core/stitching_engine.py")
print("[GUNCELLENDI] main.py")
print()
print("Simdi calistirin:")
print("  python -m unittest discover -s tests")
print("  python main.py")
