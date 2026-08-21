from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QTextEdit, QVBoxLayout

from ai.model_acceptance import ModelAcceptanceResult, evaluate_model_candidate


class AIModelCandidateReviewDialog(QDialog):
    """Read a candidate package without importing, activating, or executing its ONNX file."""

    def __init__(self, package_directory: str | Path, parent=None):
        super().__init__(parent)
        self.package_directory = Path(package_directory).expanduser().resolve()
        self.result: ModelAcceptanceResult | None = None
        self.setWindowTitle("Aday AI Model Paketi İncelemesi")
        self.setMinimumWidth(680)

        root = QVBoxLayout(self)
        title = QLabel("<b>Aday ONNX model paketinin teknik kabul incelemesi</b>")
        title.setStyleSheet("font-size: 15px;")
        root.addWidget(title)

        explanation = QLabel(
            "Bu ekran seçilen klasörü yalnızca okur. Model dosyasını çalıştırmaz, paketi kopyalamaz, "
            "etkinleştirmez veya indirmez. DICOM dosyalarına ve hasta kayıtlarına erişmez."
        )
        explanation.setObjectName("ai_candidate_review_safety_notice")
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #f1c40f; padding: 8px; background: #3b3420; border-radius: 4px;")
        root.addWidget(explanation)

        self.path_label = QLabel(str(self.package_directory))
        self.path_label.setObjectName("ai_candidate_package_path")
        self.path_label.setTextInteractionFlags(self.path_label.textInteractionFlags())
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #b8c7d9; padding: 7px; background: #1c242d; border: 1px solid #3a4654;")
        root.addWidget(self.path_label)

        self.status_label = QLabel()
        self.status_label.setObjectName("ai_candidate_review_status")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #f5f7fa; padding: 10px; background: #242424; border: 1px solid #444;")
        root.addWidget(self.status_label)

        self.details_text = QTextEdit()
        self.details_text.setObjectName("ai_candidate_review_details")
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumHeight(280)
        root.addWidget(self.details_text)

        self.refresh_button = QPushButton("Yeniden Denetle")
        self.refresh_button.clicked.connect(self.refresh_review)
        root.addWidget(self.refresh_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh_review()

    def refresh_review(self) -> None:
        self.result = evaluate_model_candidate(self.package_directory)
        accepted = self.result.accepted_for_expert_review
        state = "TEKNİK OLARAK UYGUN" if accepted else "UYGUN DEĞİL"
        color = "#43c59e" if accepted else "#e06c75"
        self.status_label.setText(
            f"<b style='color:{color}'>Kabul ön kontrolü: {state}</b><br>"
            f"{self.result.summary}<br><br>"
            "<b>Etkinleştirme:</b> YAPILMADI — paket yalnızca incelendi."
        )

        package = self.result.package
        lines = [
            "ADAY MODEL PAKETİ — SALT OKUNUR İNCELEME",
            "",
            f"Klasör: {self.package_directory}",
            f"Kabul sonucu: {state}",
            "Model çalıştırıldı: Hayır",
            "Paket etkinleştirildi: Hayır",
            "DICOM/hasta verisine erişildi: Hayır",
        ]
        if package is not None:
            lines.extend(
                [
                    "",
                    "PAKET KİMLİĞİ",
                    f"Biçim: {package.package_format}",
                    f"Model sürümü: {package.model_version}",
                    f"Model dosyası: {package.model_file}",
                    f"Bildirim SHA-256: {package.sha256}",
                ]
            )
        lines.extend(["", "BULGULAR"])
        if self.result.findings:
            lines.extend(
                f"[{finding.severity.upper()}] {finding.code}: {finding.message}"
                for finding in self.result.findings
            )
        else:
            lines.append("Bulgu yok.")
        self.details_text.setPlainText("\n".join(lines))
