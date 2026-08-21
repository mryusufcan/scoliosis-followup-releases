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
    raise SystemExit(
        "[HATA] modular_app/core/stitching_engine.py bulunamadi. "
        "Once Asama 1 ve Asama 2 uygulanmali."
    )

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = RESTORE / f"stitch_engine_stage3_{stamp}"
backup.mkdir(parents=True, exist_ok=True)

shutil.copy2(MAIN, backup / "main.py")
shutil.copy2(ENGINE, backup / "stitching_engine.py")

main_text = MAIN.read_text(encoding="utf-8-sig")
engine_text = ENGINE.read_text(encoding="utf-8-sig")

engine_method = '\n    def auto_estimate_offset(\n        self,\n        arr_top,\n        arr_bottom,\n        min_ratio=0.12,\n        max_ratio=0.32,\n        max_dx=50,\n        cv=None,\n    ):\n        try:\n            h_top, w_top = arr_top.shape[:2]\n            h_bot, w_bot = arr_bottom.shape[:2]\n            band_w = min(w_top, w_bot)\n\n            min_overlap = int(h_top * min_ratio)\n            max_overlap = int(h_top * max_ratio)\n\n            if h_top < 10 or h_bot < 10 or max_overlap <= min_overlap:\n                return 0.0, float(max(1, int(h_top * 0.20))), 0.0, arr_bottom\n\n            window_h = min(120, h_top, h_bot)\n            max_feature_w = 640\n            scale = min(1.0, max_feature_w / float(max(1, band_w)))\n            feat_w = max(64, int(round(band_w * scale)))\n            feat_h = max(32, int(round(window_h * scale)))\n\n            def make_feature(region):\n                gray = self.to_gray(region).astype(np.float32)\n\n                if cv is not None:\n                    gray = cv.resize(gray, (feat_w, feat_h), interpolation=cv.INTER_AREA)\n                    gray = cv.GaussianBlur(gray, (3, 3), 0)\n                    gx = cv.Sobel(gray, cv.CV_32F, 1, 0, ksize=3)\n                    gy = cv.Sobel(gray, cv.CV_32F, 0, 1, ksize=3)\n                    feat = cv.magnitude(gx, gy)\n                else:\n                    gray = self.resize_gray_fast(gray, feat_w, feat_h)\n                    feat = self.sobel_magnitude(gray)\n\n                feat -= feat.mean()\n                std = feat.std()\n                if std > 1e-6:\n                    feat /= std\n                return feat.astype(np.float32)\n\n            top_region = arr_top[max(0, h_top - window_h):h_top, :band_w]\n            top_feat = make_feature(top_region)\n\n            win = np.hanning(feat_h)[:, None] * np.hanning(feat_w)[None, :]\n            top_win = top_feat * win\n            top_fft = np.fft.fft2(top_win)\n\n            best_score = -1.0\n            best_dy = int(h_top * 0.20)\n            best_dx = 0\n\n            for trial_overlap in range(min_overlap, max_overlap + 1, 5):\n                if trial_overlap < window_h or trial_overlap > h_bot:\n                    continue\n\n                y2 = trial_overlap\n                y1 = y2 - window_h\n                bot_region = arr_bottom[y1:y2, :band_w]\n\n                if bot_region.shape[0] != window_h:\n                    continue\n\n                bot_feat = make_feature(bot_region)\n                bot_win = bot_feat * win\n                bot_fft = np.fft.fft2(bot_win)\n\n                r_fft = top_fft * np.conj(bot_fft)\n                r_fft /= np.abs(r_fft) + 1e-8\n                corr = np.fft.fftshift(np.fft.ifft2(r_fft).real)\n\n                peak_idx = np.unravel_index(np.argmax(corr), corr.shape)\n                peak_val = float(corr[peak_idx])\n                mean_abs = float(np.mean(np.abs(corr))) + 1e-8\n                score = float(np.clip(\n                    peak_val / (mean_abs * 50.0),\n                    0.0,\n                    1.0,\n                ))\n\n                dy_feat = peak_idx[0] - feat_h // 2\n                dx_feat = peak_idx[1] - feat_w // 2\n\n                dy = int(round(dy_feat / scale))\n                dx = int(round(dx_feat / scale))\n                calc_dy = trial_overlap + dy\n\n                if score > best_score and min_overlap <= calc_dy <= max_overlap:\n                    best_score = score\n                    best_dy = calc_dy\n                    best_dx = dx\n\n            best_dx = float(np.clip(best_dx, -max_dx, max_dx))\n            best_dy = float(np.clip(best_dy, min_overlap, max_overlap))\n            return best_dx, best_dy, best_score, arr_bottom\n\n        except Exception as exc:\n            print(f"Dinamik cakisma hizalamasi basarisiz: {exc}")\n            fallback_dy = float(int(arr_top.shape[0] * 0.20))\n            return 0.0, fallback_dy, 0.0, arr_bottom\n'
if "def auto_estimate_offset(" not in engine_text:
    engine_text = engine_text.rstrip() + "\n" + engine_method + "\n"

ast.parse(engine_text)

tree = ast.parse(main_text)
app_class = next(
    (
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ScoliosisFollowUpApp"
    ),
    None,
)
if app_class is None:
    raise RuntimeError("ScoliosisFollowUpApp sinifi bulunamadi.")

target = next(
    (
        node for node in app_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_auto_estimate_offset"
    ),
    None,
)
if target is None:
    raise RuntimeError(
        "_auto_estimate_offset bulunamadi. "
        "main.py beklenen surumden farkli."
    )

replacement = '\n    def _auto_estimate_offset(\n        self,\n        arr_top,\n        arr_bottom,\n        min_ratio=0.12,\n        max_ratio=0.32,\n        max_dx=50,\n    ):\n        cv = optional_cv2()\n        return self.stitch_engine.auto_estimate_offset(\n            arr_top,\n            arr_bottom,\n            min_ratio=min_ratio,\n            max_ratio=max_ratio,\n            max_dx=max_dx,\n            cv=cv,\n        )\n'
lines = main_text.splitlines(keepends=True)

start = min(
    [target.lineno] + [d.lineno for d in target.decorator_list]
) - 1
end = target.end_lineno

lines[start:end] = [
    replacement if replacement.endswith("\n") else replacement + "\n"
]

new_main = "".join(lines)
ast.parse(new_main)

ENGINE.write_text(engine_text, encoding="utf-8")
MAIN.write_text(new_main, encoding="utf-8")

print()
print("=== STITCHING REFACTOR | ASAMA 3 TAMAMLANDI ===")
print(f"[YEDEK] {backup}")
print("[GUNCELLENDI] modular_app/core/stitching_engine.py")
print("[GUNCELLENDI] main.py")
print()
print("Motora tasindi:")
print("  - dinamik overlap arama")
print("  - feature resize")
print("  - Sobel feature hesaplama")
print("  - FFT phase correlation")
print("  - dx / dy tahmini")
print("  - guven skoru")
print("  - OpenCV / NumPy fallback")
print()
print("Simdi:")
print("  python -m unittest discover -s tests")
print("  python main.py")
