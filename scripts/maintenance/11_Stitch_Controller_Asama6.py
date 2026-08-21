from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
CONTROLLER = ROOT / "modular_app" / "core" / "stitch_controller.py"
RESTORE = ROOT / ".restore_points"

PROPERTY_BLOCK = '\n    @property\n    def manual_stage_index(self):\n        controller = getattr(self, "stitch_controller", None)\n        if controller is not None:\n            return controller.manual_stage_index\n        return getattr(self, "_manual_stage_index_fallback", 0)\n\n    @manual_stage_index.setter\n    def manual_stage_index(self, value):\n        controller = getattr(self, "stitch_controller", None)\n        if controller is not None:\n            controller.manual_stage_index = int(value)\n        else:\n            self._manual_stage_index_fallback = int(value)\n\n    @property\n    def manual_points(self):\n        controller = getattr(self, "stitch_controller", None)\n        if controller is not None:\n            return controller.manual_points\n        return getattr(self, "_manual_points_fallback", {})\n\n    @manual_points.setter\n    def manual_points(self, value):\n        controller = getattr(self, "stitch_controller", None)\n        if controller is not None:\n            controller.manual_points = value\n        else:\n            self._manual_points_fallback = value\n\n    @property\n    def manual_junction_offsets(self):\n        controller = getattr(self, "stitch_controller", None)\n        if controller is not None:\n            return controller.manual_junction_offsets\n        return getattr(self, "_manual_junction_offsets_fallback", {})\n\n    @manual_junction_offsets.setter\n    def manual_junction_offsets(self, value):\n        controller = getattr(self, "stitch_controller", None)\n        if controller is not None:\n            controller.manual_junction_offsets = value\n        else:\n            self._manual_junction_offsets_fallback = value\n\n'
SYNC_BLOCK = '        self.stitch_controller.manual_stage_index = getattr(\n            self, "_manual_stage_index_fallback", 0\n        )\n        self.stitch_controller.manual_points = getattr(\n            self, "_manual_points_fallback", {}\n        )\n        self.stitch_controller.manual_junction_offsets = getattr(\n            self, "_manual_junction_offsets_fallback", {}\n        )\n'

if not MAIN.is_file():
    raise SystemExit(f"[HATA] main.py bulunamadi: {MAIN}")

if not CONTROLLER.is_file():
    raise SystemExit(
        "[HATA] stitch_controller.py bulunamadi. "
        "Once Asama 4 ve 5 uygulanmali."
    )

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = RESTORE / f"stitch_controller_stage6_{stamp}"
backup.mkdir(parents=True, exist_ok=True)

shutil.copy2(MAIN, backup / "main.py")
shutil.copy2(CONTROLLER, backup / "stitch_controller.py")

main_text = MAIN.read_text(encoding="utf-8-sig")
controller_text = CONTROLLER.read_text(encoding="utf-8-sig")

# 1) Controller state alanlarini ekle
tree_c = ast.parse(controller_text)
controller_class = next(
    (
        node for node in tree_c.body
        if isinstance(node, ast.ClassDef)
        and node.name == "StitchController"
    ),
    None,
)
if controller_class is None:
    raise RuntimeError("StitchController sinifi bulunamadi.")

init_func = next(
    (
        node for node in controller_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "__init__"
    ),
    None,
)
if init_func is None:
    raise RuntimeError("StitchController.__init__ bulunamadi.")

if "self.manual_stage_index = 0" not in controller_text:
    lines = controller_text.splitlines(keepends=True)
    insert_at = init_func.end_lineno
    state_block = (
        "        self.manual_stage_index = 0\n"
        "        self.manual_points = {}\n"
        "        self.manual_junction_offsets = {}\n"
    )
    lines[insert_at:insert_at] = [state_block]
    controller_text = "".join(lines)

# 2) main.py compatibility property'leri
if "def manual_stage_index(self):" not in main_text:
    tree_m = ast.parse(main_text)
    app_class = next(
        (
            node for node in tree_m.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ScoliosisFollowUpApp"
        ),
        None,
    )
    if app_class is None:
        raise RuntimeError("ScoliosisFollowUpApp sinifi bulunamadi.")

    manual_pairs = next(
        (
            node for node in app_class.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_manual_pairs"
        ),
        None,
    )
    if manual_pairs is None:
        raise RuntimeError("_manual_pairs bulunamadi.")

    lines = main_text.splitlines(keepends=True)
    insert_at = manual_pairs.lineno - 1
    lines[insert_at:insert_at] = [PROPERTY_BLOCK]
    main_text = "".join(lines)

# 3) Controller olustugunda fallback state'i aktar
controller_init_line = "        self.stitch_controller = StitchController(self.stitch_engine)\n"

if controller_init_line not in main_text:
    raise RuntimeError(
        "StitchController baslatma satiri bulunamadi. "
        "Asama 4 uygulanmis olmayabilir."
    )

if "self.stitch_controller.manual_stage_index = getattr(" not in main_text:
    main_text = main_text.replace(
        controller_init_line,
        controller_init_line + SYNC_BLOCK,
        1,
    )

# Syntax kontrolleri
ast.parse(controller_text)
ast.parse(main_text)

CONTROLLER.write_text(controller_text, encoding="utf-8")
MAIN.write_text(main_text, encoding="utf-8")

print()
print("=== STITCH CONTROLLER | ASAMA 6 TAMAMLANDI ===")
print(f"[YEDEK] {backup}")
print("[GUNCELLENDI] modular_app/core/stitch_controller.py")
print("[GUNCELLENDI] main.py")
print()
print("Gercek state artik StitchController'da:")
print("  - manual_stage_index")
print("  - manual_points")
print("  - manual_junction_offsets")
print()
print("main.py compatibility property'leri ile eski self.manual_*")
print("cagirilari bozulmadan devam eder.")
print()
print("Kontrol:")
print("  python -m unittest discover -s tests")
print("  python main.py")
