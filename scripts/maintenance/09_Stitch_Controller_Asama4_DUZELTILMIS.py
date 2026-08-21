from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

CONTROLLER_CODE = 'from __future__ import annotations\n\nfrom dataclasses import dataclass\nimport math\n\nimport numpy as np\n\n\n@dataclass(frozen=True)\nclass ManualAlignmentResult:\n    dx: float\n    target_y: float\n    angle_deg: float\n    dy_adjust: float\n\n\nclass StitchController:\n    """Stitching durum/geometri kararlarini UI\'dan ayiran katman."""\n\n    def __init__(self, engine):\n        self.engine = engine\n\n    @staticmethod\n    def calculate_manual_alignment(\n        fixed_points,\n        moving_points,\n        *,\n        moving_width,\n        moving_height,\n        top_height,\n        overlap_px,\n        max_angle_deg=12.0,\n        min_point_distance=3.0,\n    ):\n        """2+2 anatomik noktadan rigid manuel hizalama hesaplar.\n\n        fixed_points: sabit goruntudeki iki nokta\n        moving_points: hareketli goruntudeki ayni iki anatomik nokta\n        """\n        if len(fixed_points) < 2 or len(moving_points) < 2:\n            raise ValueError("2+2 nokta gerekli.")\n\n        p0 = np.asarray(fixed_points[0], dtype=np.float64)\n        p1 = np.asarray(fixed_points[1], dtype=np.float64)\n        q0 = np.asarray(moving_points[0], dtype=np.float64)\n        q1 = np.asarray(moving_points[1], dtype=np.float64)\n\n        v_src = q1 - q0\n        v_dst = p1 - p0\n\n        src_len = float(np.linalg.norm(v_src))\n        dst_len = float(np.linalg.norm(v_dst))\n\n        if src_len < float(min_point_distance) or dst_len < float(min_point_distance):\n            raise ValueError("POINTS_TOO_CLOSE")\n\n        angle_src = math.atan2(v_src[1], v_src[0])\n        angle_dst = math.atan2(v_dst[1], v_dst[0])\n        angle_deg = math.degrees(angle_dst - angle_src)\n        angle_deg = float(np.clip(angle_deg, -max_angle_deg, max_angle_deg))\n\n        cx = float(moving_width) / 2.0\n        cy = float(moving_height) / 2.0\n\n        a = math.radians(angle_deg)\n        ca = math.cos(a)\n        sa = math.sin(a)\n\n        q0r_x = ca * (q0[0] - cx) - sa * (q0[1] - cy) + cx\n        q0r_y = sa * (q0[0] - cx) + ca * (q0[1] - cy) + cy\n\n        target_x = float(p0[0] - q0r_x)\n        target_y = float(p0[1] - q0r_y)\n\n        dy_adjust = target_y - (float(top_height) - float(overlap_px))\n\n        return ManualAlignmentResult(\n            dx=float(target_x),\n            target_y=float(target_y),\n            angle_deg=float(angle_deg),\n            dy_adjust=float(dy_adjust),\n        )\n'
REPLACEMENT_BLOCK = '        try:\n            alignment = self.stitch_controller.calculate_manual_alignment(\n                pts0,\n                pts1,\n                moving_width=self._pick_pixmaps[1].width(),\n                moving_height=self._pick_pixmaps[1].height(),\n                top_height=self._pick_pixmaps[0].height(),\n                overlap_px=self.OVERLAP_PX,\n            )\n        except ValueError as exc:\n            if str(exc) == "POINTS_TOO_CLOSE":\n                self.statusBar().showMessage(\n                    "İki nokta birbirine çok yakın. Lütfen daha belirgin iki anatomik nokta seçin."\n                )\n                return\n            raise\n\n        upper, lower = self._manual_pair_parts\n\n        self.manual_junction_offsets[(upper, lower)] = (\n            alignment.dx,\n            alignment.target_y,\n            alignment.angle_deg,\n        )\n\n        dx_adjust = alignment.dx\n        dy_adjust = alignment.dy_adjust\n        angle_deg = alignment.angle_deg\n'

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
CORE = ROOT / "modular_app" / "core"
ENGINE = CORE / "stitching_engine.py"
CONTROLLER = CORE / "stitch_controller.py"
RESTORE = ROOT / ".restore_points"

if not MAIN.is_file():
    raise SystemExit(f"[HATA] main.py bulunamadi: {MAIN}")

if not ENGINE.is_file():
    raise SystemExit(
        "[HATA] stitching_engine.py bulunamadi. "
        "Once Asama 1-3 uygulanmali."
    )

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = RESTORE / f"stitch_controller_stage4_{stamp}"
backup.mkdir(parents=True, exist_ok=True)

shutil.copy2(MAIN, backup / "main.py")
shutil.copy2(ENGINE, backup / "stitching_engine.py")

if CONTROLLER.exists():
    shutil.copy2(CONTROLLER, backup / "stitch_controller.py")

CONTROLLER.write_text(CONTROLLER_CODE, encoding="utf-8")

main_text = MAIN.read_text(encoding="utf-8-sig")

# ------------------------------------------------------------
# Import ekle
# ------------------------------------------------------------
import_line = "from modular_app.core.stitch_controller import StitchController\n"

if import_line not in main_text:
    engine_import = "from modular_app.core.stitching_engine import StitchingEngine\n"
    if engine_import not in main_text:
        raise RuntimeError(
            "StitchingEngine importu bulunamadi. "
            "Asama 1 uygulanmis olmayabilir."
        )
    main_text = main_text.replace(
        engine_import,
        engine_import + import_line,
        1,
    )

# ------------------------------------------------------------
# Controller instance ekle
# ------------------------------------------------------------
controller_init = "        self.stitch_controller = StitchController(self.stitch_engine)\n"

if controller_init not in main_text:
    engine_init = "        self.stitch_engine = StitchingEngine(mask_cache=self._stitch_mask_cache)\n"
    if engine_init not in main_text:
        raise RuntimeError(
            "stitch_engine baslatma satiri bulunamadi."
        )
    main_text = main_text.replace(
        engine_init,
        engine_init + controller_init,
        1,
    )

# ------------------------------------------------------------
# handle_manual_point_click icindeki geometri blogunu degistir.
# AST ile fonksiyon araligini bul, markerlarla sadece hedef kismi kes.
# ------------------------------------------------------------
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
    raise RuntimeError("ScoliosisFollowUpApp bulunamadi.")

target = next(
    (
        node for node in app_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "handle_manual_point_click"
    ),
    None,
)

if target is None:
    raise RuntimeError("handle_manual_point_click bulunamadi.")

lines = main_text.splitlines(keepends=True)

start_idx = None
end_idx = None

for i in range(target.lineno - 1, target.end_lineno):
    line = lines[i]

    if start_idx is None and "p0 = np.asarray(pts0[0]" in line:
        start_idx = i

    if start_idx is not None and "self.is_stitched_completed = True" in line:
        end_idx = i - 1
        break

if start_idx is None or end_idx is None:
    raise RuntimeError(
        "Manuel geometri blogu bulunamadi. "
        "main.py beklenen surumden farkli; dosya degistirilmedi."
    )

lines[start_idx:end_idx + 1] = [REPLACEMENT_BLOCK]

new_main = "".join(lines)

# Syntax kontrolleri
ast.parse(CONTROLLER_CODE)
ast.parse(new_main)

MAIN.write_text(new_main, encoding="utf-8")

print()
print("=== STITCHING REFACTOR | ASAMA 4 TAMAMLANDI ===")
print(f"[YEDEK] {backup}")
print("[OLUSTU] modular_app/core/stitch_controller.py")
print("[GUNCELLENDI] main.py")
print()
print("Controller'a tasinanlar:")
print("  - 2+2 nokta vektor geometrisi")
print("  - nokta mesafe kontrolu")
print("  - manuel aci hesabi")
print("  - aci sinirlama (+/-12 derece)")
print("  - hareketli goruntuyu merkez etrafinda donus hesabi")
print("  - dx / target_y / dy_adjust hesabi")
print()
print("main.py'de kalan:")
print("  - mouse tiklamasi")
print("  - marker cizimi")
print("  - status mesajlari")
print("  - Qt buton/pencere davranisi")
print()
print("Simdi:")
print("  python -m unittest discover -s tests")
print("  python main.py")
