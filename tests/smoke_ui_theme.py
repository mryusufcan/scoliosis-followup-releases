import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from main import ScoliosisFollowUpApp, apply_app_theme
from modular_app.run_modular import install_modules


app = QApplication.instance() or QApplication([])
AppClass = install_modules(ScoliosisFollowUpApp)
window = AppClass()

apply_app_theme(app, "dark")
assert "#11161D" in app.styleSheet()
assert "#0B0F14" in app.styleSheet()
apply_app_theme(app, "light")
assert "#F4F7FA" in app.styleSheet()
assert "#11161D" not in app.styleSheet()
apply_app_theme(app, "dark")
assert window.central_widget.objectName() == "appRoot"
assert window.menuBar().objectName() == "mainMenuBar"
assert window.statusBar().objectName() == "mainStatusBar"
assert window.minimumWidth() == 1180
assert window.study_search.objectName() == "studySearch"
assert window.study_tree_widget.objectName() == "studyTree"
assert window.viewer_file_tree.objectName() == "viewerFileTree"
assert window.btn_viewer_cobb.property("uiMeasurement") is True
assert window.btn_viewer_length.property("uiMeasurement") is True

print("UI_THEME_SMOKE_OK")
window.close()
app.processEvents()
