from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
CONTROLLER = ROOT / "modular_app" / "core" / "stitch_controller.py"
RESTORE = ROOT / ".restore_points"

if not MAIN.is_file():
    raise SystemExit(f"[HATA] main.py bulunamadi: {MAIN}")

if not CONTROLLER.is_file():
    raise SystemExit(
        "[HATA] stitch_controller.py bulunamadi. "
        "Once Asama 4 uygulanmali."
    )

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = RESTORE / f"stitch_controller_stage5_{stamp}"
backup.mkdir(parents=True, exist_ok=True)

shutil.copy2(MAIN, backup / "main.py")
shutil.copy2(CONTROLLER, backup / "stitch_controller.py")

main_text = MAIN.read_text(encoding="utf-8-sig")
controller_text = CONTROLLER.read_text(encoding="utf-8-sig")

ADDITIONS = '\n    @staticmethod\n    def active_pairs(stitch_files):\n        order = ("servical", "dorsal", "lumbar")\n        active = [part for part in order if stitch_files.get(part)]\n        return list(zip(active[:-1], active[1:]))\n\n    @staticmethod\n    def fresh_manual_state():\n        return {\n            "stage_index": 0,\n            "points": {},\n            "junction_offsets": {},\n        }\n\n    @staticmethod\n    def reset_points_state():\n        return {\n            "stage_index": 0,\n            "points": {},\n        }\n\n    @staticmethod\n    def remove_part_from_junction_offsets(junction_offsets, part_name):\n        return {\n            key: value\n            for key, value in junction_offsets.items()\n            if part_name not in key\n        }\n\n    @staticmethod\n    def can_advance_stage(stage_index, pairs, manual_points):\n        if not pairs or stage_index >= len(pairs):\n            return False\n        return (\n            len(manual_points.get(0, [])) >= 2\n            and len(manual_points.get(1, [])) >= 2\n        )\n\n    @staticmethod\n    def next_stage_index(stage_index, pairs):\n        candidate = int(stage_index) + 1\n        if candidate < len(pairs):\n            return candidate\n        return None\n'

if "def active_pairs(" not in controller_text:
    controller_text = controller_text.rstrip() + "\n" + ADDITIONS + "\n"

ast.parse(controller_text)

old_manual_pairs = """    def _manual_pairs(self):
        active = [p for p in ['servical', 'dorsal', 'lumbar'] if self.stitch_files.get(p) is not None]
        return list(zip(active[:-1], active[1:]))
"""
new_manual_pairs = """    def _manual_pairs(self):
        return self.stitch_controller.active_pairs(self.stitch_files)
"""
if old_manual_pairs in main_text:
    main_text = main_text.replace(old_manual_pairs, new_manual_pairs, 1)
elif new_manual_pairs not in main_text:
    raise RuntimeError("_manual_pairs beklenen bicimde bulunamadi.")

old_reset = """        self.manual_stage_index = 0
        self.manual_points = {}
        self.manual_junction_offsets = {}
        self.is_stitched_completed = False
"""
new_reset = """        manual_state = self.stitch_controller.fresh_manual_state()
        self.manual_stage_index = manual_state["stage_index"]
        self.manual_points = manual_state["points"]
        self.manual_junction_offsets = manual_state["junction_offsets"]
        self.is_stitched_completed = False
"""
if old_reset in main_text:
    main_text = main_text.replace(old_reset, new_reset)

old_mode_reset = """            self.manual_stage_index = 0
            self.manual_points = {}
            self._manual_point_marker_by_part = {}
"""
new_mode_reset = """            manual_state = self.stitch_controller.reset_points_state()
            self.manual_stage_index = manual_state["stage_index"]
            self.manual_points = manual_state["points"]
            self._manual_point_marker_by_part = {}
"""
if old_mode_reset in main_text:
    main_text = main_text.replace(old_mode_reset, new_mode_reset, 1)

old_filter = """        self.manual_junction_offsets = {
            k: v for k, v in self.manual_junction_offsets.items()
            if part_name not in k
        }
        self.manual_stage_index = 0
"""
new_filter = """        self.manual_junction_offsets = (
            self.stitch_controller.remove_part_from_junction_offsets(
                self.manual_junction_offsets,
                part_name,
            )
        )
        self.manual_stage_index = 0
"""
if old_filter in main_text:
    main_text = main_text.replace(old_filter, new_filter, 1)

old_advance_guard = """        pairs=self._manual_pairs()
        if not pairs or self.manual_stage_index >= len(pairs):
            return
        if len(self.manual_points.get(0,[])) < 2 or len(self.manual_points.get(1,[])) < 2:
            QMessageBox.information(self,"Manuel Hizalama","Önce SABİT görüntüde 2 ve HAREKETLİ görüntüde 2 karşılık gelen nokta seçin.")
            return
"""
new_advance_guard = """        pairs = self._manual_pairs()
        if not self.stitch_controller.can_advance_stage(
            self.manual_stage_index,
            pairs,
            self.manual_points,
        ):
            QMessageBox.information(
                self,
                "Manuel Hizalama",
                "Önce SABİT görüntüde 2 ve HAREKETLİ görüntüde 2 karşılık gelen nokta seçin.",
            )
            return
"""
if old_advance_guard in main_text:
    main_text = main_text.replace(old_advance_guard, new_advance_guard, 1)

old_next = """        if self.manual_stage_index + 1 < len(pairs):
            upper, lower = pairs[self.manual_stage_index]
            self.manual_stage_index += 1
            self.manual_points={}
"""
new_next = """        next_stage = self.stitch_controller.next_stage_index(
            self.manual_stage_index,
            pairs,
        )
        if next_stage is not None:
            upper, lower = pairs[self.manual_stage_index]
            self.manual_stage_index = next_stage
            self.manual_points = {}
"""
if old_next in main_text:
    main_text = main_text.replace(old_next, new_next, 1)

ast.parse(main_text)
ast.parse(controller_text)

CONTROLLER.write_text(controller_text, encoding="utf-8")
MAIN.write_text(main_text, encoding="utf-8")

print()
print("=== STITCH CONTROLLER | ASAMA 5 TAMAMLANDI ===")
print(f"[YEDEK] {backup}")
print("[GUNCELLENDI] modular_app/core/stitch_controller.py")
print("[GUNCELLENDI] main.py")
print()
print("Controller'a eklenenler:")
print("  - aktif komsu parca ciftleri")
print("  - manuel oturum reset state")
print("  - nokta/stage reset state")
print("  - parca silinince junction filtreleme")
print("  - sonraki asamaya gecis kontrolu")
print("  - sonraki asama indexi")
print()
print("Simdi:")
print("  python -m unittest discover -s tests")
print("  python main.py")
