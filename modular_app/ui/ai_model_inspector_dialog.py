from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QTextEdit, QVBoxLayout

from ai.model_acceptance import evaluate_model_candidate
from ai.model_runtime import LocalCobbModel


class AIModelInspectorDialog(QDialog):
    """Read-only local model package inspection; it never downloads or changes a model."""

    def __init__(self, model: LocalCobbModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("AI Model Paketi Denetimi")
        self.setMinimumWidth(620)

        root = QVBoxLayout(self)
        title = QLabel("<b>Yerel AI modelinin güvenlik ve kaynak bilgileri</b>")
        title.setStyleSheet("font-size: 15px;")
        root.addWidget(title)

        explanation = QLabel(
            "Bu ekran modeli indirmez veya değiştirmez. Yalnızca model dosyasının bütünlüğünü, "
            "sürümünü ve varsa model kartı bilgisini gösterir."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #f1c40f; padding: 8px; background: #3b3420; border-radius: 4px;")
        root.addWidget(explanation)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #f5f7fa; padding: 10px; background: #242424; border: 1px solid #444;")
        root.addWidget(self.status_label)

        self.card_text = QTextEdit()
        self.card_text.setObjectName("ai_model_card_text")
        self.card_text.setReadOnly(True)
        self.card_text.setMinimumHeight(230)
        root.addWidget(self.card_text)

        self.refresh_button = QPushButton("Durumu Yenile")
        self.refresh_button.clicked.connect(self.refresh_status)
        root.addWidget(self.refresh_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh_status()

    def refresh_status(self) -> None:
        status = self.model.inspect()
        availability = "Kullanıma hazır" if status.ready else "Çalıştırılamaz"
        details = [
            f"<b>Durum:</b> {availability}",
            f"<b>Açıklama:</b> {status.message}",
        ]
        if status.model_version:
            details.append(f"<b>Model sürümü:</b> {status.model_version}")
        if status.sha256:
            details.append(f"<b>Dosya özeti:</b> {status.sha256[:16]}…")
        if status.model_path:
            details.append(f"<b>Yerel model dosyası:</b> {status.model_path}")
        self.status_label.setText("<br>".join(details))

        package = status.package
        if package is None:
            self.card_text.setPlainText(
                "Model kartı kullanılamıyor. Model dosyası veya manifest bulunmadığı için ayrıntılı inceleme yapılamadı."
            )
            return
        if not package.is_v2 or package.model_card is None:
            self.card_text.setPlainText(
                "Model paketi biçimi: V1\n\n"
                "Bu eski paket yalnızca temel dosya bütünlüğü kontrolünden geçer. "
                "Kaynak, lisans, desteklenen görüntü türü ve bilinen hata durumları için V2 model kartı gerekir."
            )
            return

        card = package.model_card
        acceptance_lines: list[str] = []
        model_directory = getattr(self.model, "model_directory", None)
        if model_directory:
            acceptance = evaluate_model_candidate(model_directory)
            if acceptance.accepted_for_expert_review:
                acceptance_lines = ["KABUL ÖN KONTROLÜ", "Uzman incelemeli POC için teknik olarak hazır."]
            else:
                acceptance_lines = [
                    "KABUL ÖN KONTROLÜ",
                    "Henüz uzman incelemeli POC için hazır değil.",
                    *[f"• {finding.message}" for finding in acceptance.findings],
                ]
            if acceptance.report:
                metrics = acceptance.report.get("metrics", {})
                if isinstance(metrics, dict):
                    landmark_error = metrics.get("landmark_error_px_median")
                    cobb_mae = metrics.get("cobb_mae_degrees")
                    acceptance_lines.extend(
                        [
                            "",
                            "DOĞRULAMA RAPORU",
                            f"İnceleyen: {acceptance.report.get('reviewed_by', 'Belirtilmedi')}",
                            f"Landmark medyan hatası: {landmark_error if landmark_error is not None else 'Belirtilmedi'} px",
                            f"Cobb MAE: {cobb_mae if cobb_mae is not None else 'Belirtilmedi'}°",
                        ]
                    )
        text = "\n".join(
            [
                "MODEL KARTI — V2",
                "",
                f"Kaynak depo: {package.source_repository}",
                f"Kaynak commit: {package.source_commit}",
                f"Kod lisansı: {package.source_license}",
                f"Model ağırlığı lisansı: {package.weights_license}",
                f"Veri lisansı: {package.dataset_license}",
                f"ONNX opset: {package.onnx_opset}",
                "",
                "Amaç:",
                card.intended_use,
                "",
                "Doğrulama özeti:",
                card.validation_summary,
                "",
                "Desteklenen modaliteler: " + ", ".join(card.supported_modalities),
                "Desteklenen görüntü yönleri: " + ", ".join(card.supported_views),
                "Hariç tutulan durumlar: " + (", ".join(card.excluded_conditions) or "Belirtilmedi"),
                "",
                "Bilinen hata durumları:",
                *[f"• {item}" for item in card.known_failure_modes],
                "",
                *acceptance_lines,
            ]
        )
        self.card_text.setPlainText(text)
