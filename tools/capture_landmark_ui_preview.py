"""Capture non-interactive offscreen previews of the landmark guide and dialog."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from ai.model_runtime import AIModelStatus
from modular_app.ui.ai_landmark_assistant_dialog import AILandmarkAssistantDialog
from modular_app.ui.user_guide_dialog import UserGuideDialog


class PreviewLandmarkModel:
    def inspect(self):
        return AIModelStatus(
            True,
            "experimental_ready",
            "DENEYSEL: Yerel landmark taslağı hazır. V2 kabul eksikleri görünür kalır; ölçüm kaydı oluşturulmaz.",
            model_version="vertebra-landmark-68-onnx-candidate-20260820",
        )


def capture(widget, output: Path) -> None:
    widget.show()
    QApplication.processEvents()
    pixmap = widget.grab()
    if pixmap.isNull() or not pixmap.save(str(output), "PNG"):
        raise RuntimeError(f"Ekran görüntüsü yazılamadı: {output}")
    widget.close()


def main() -> int:
    output_dir = ROOT / "docs" / "reports" / "screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    guide = UserGuideDialog()
    guide.search.setText("68-Landmark")
    capture(guide, output_dir / "experimental_landmark_user_guide.png")
    dialog = AILandmarkAssistantDialog(PreviewLandmarkModel(), "C:\\izinli_veri\\deidentified_ap_or_pa.dcm")
    capture(dialog, output_dir / "experimental_landmark_dialog.png")
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
