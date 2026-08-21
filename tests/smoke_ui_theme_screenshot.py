import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from main import ScoliosisFollowUpApp
from modular_app.run_modular import install_modules


app = QApplication.instance() or QApplication([])
AppClass = install_modules(ScoliosisFollowUpApp)
window = AppClass()
window.resize(1400, 900)
window.show()
app.processEvents()

output_dir = PROJECT_ROOT / "docs"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "ui_dark_theme_smoke.png"
window.grab().save(str(output_path))
print(output_path)
window.close()
app.processEvents()
