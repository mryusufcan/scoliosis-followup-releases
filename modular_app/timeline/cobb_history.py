from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository
from modular_app.services.measurement_labels import display_measurement_source
from modular_app.ui.ui_clarity import configure_action, create_context_banner



def _pair_text(row: dict) -> str:
    upper = str(row.get("upper_vertebra", "") or "").strip()
    lower = str(row.get("lower_vertebra", "") or "").strip()
    return f"{upper}–{lower}" if upper and lower else "—"


def _direction_text(row: dict) -> str:
    value = str(row.get("curve_direction", "") or "").strip()
    return value if value and value != "Belirtilmedi" else "—"


def _delta_by_measurement_id(rows: list[dict]) -> dict[int, float | None]:
    """Calculate delta only against the previous chronological record of the same pair."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        upper = str(row.get("upper_vertebra", "") or "").strip()
        lower = str(row.get("lower_vertebra", "") or "").strip()
        direction = str(row.get("curve_direction", "") or "").strip()
        if not upper or not lower:
            continue
        groups.setdefault((upper, lower, direction), []).append(row)

    result: dict[int, float | None] = {}
    for pair_rows in groups.values():
        chronological = sorted(
            pair_rows,
            key=lambda row: (
                str(row.get("exam_date", "") or ""),
                str(row.get("created_at", "") or ""),
                int(row.get("id", 0) or 0),
            ),
        )
        previous = None
        for row in chronological:
            row_id = int(row.get("id", 0) or 0)
            angle = float(row.get("angle_degrees", 0.0))
            result[row_id] = None if previous is None else angle - previous
            previous = angle
    return result


class CobbHistoryDialog(QDialog):
    """Cobb history with local clinician verification and immutable approved records."""

    def __init__(self, repository: ExamRepository, patient_id: str, actor: str = "", actor_role: str = "", parent=None):
        super().__init__(parent)
        self.repository = repository
        self.patient_id = str(patient_id)
        self.actor, self.actor_role = str(actor), str(actor_role)
        self.setWindowTitle("Cobb Ölçüm Geçmişi")
        self.setObjectName("workflowDialog")
        self.resize(1120, 430)
        layout = QVBoxLayout(self)
        context_banner, self.context_label = create_context_banner(
            "Cobb Ölçüm Geçmişi",
            f"PatientID: {patient_id} · Bir ölçüm seçin; kanıtı görüntüleyin, düzenleyin veya doğrulayın.",
            object_name="workflowContextBanner",
        )
        layout.addWidget(context_banner)
        subtitle = QLabel(f"<b>Hasta ölçümleri</b>  |  PatientID: {patient_id}")
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(subtitle)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Tarih", "Görüntü", "Vertebra", "Eğri yönü", "Taraf", "Cobb açısı", "Δ",
            "Durum", "Doğrulayan", "Doğrulama zamanı", "Not"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.rows = repository.list_cobb_measurements(patient_id)
        delta_map = _delta_by_measurement_id(self.rows)
        for row in self.rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            delta = delta_map.get(int(row.get("id", 0) or 0))
            delta_text = "—" if delta is None else f"{delta:+.2f}°"
            values = [
                row.get("exam_date", "") or row.get("created_at", ""),
                Path(row.get("dicom_path", "")).name,
                _pair_text(row),
                _direction_text(row),
                display_measurement_source(row.get("side", "")),
                f"{float(row.get('angle_degrees', 0.0)):.2f}°",
                delta_text,
                "Kilitli" if bool(row.get("is_locked")) else "Taslak",
                str(row.get("verified_by", "")) or "—",
                str(row.get("verified_at", "")) or "—",
                str(row.get("verification_note", "")) or "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(256, row.get("id"))
                self.table.setItem(index, column, item)
        layout.addWidget(self.table)
        self.summary = QLabel(self._summary_text(self.rows))
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#95a5a6;")
        layout.addWidget(self.summary)
        buttons = QHBoxLayout()
        edit_button = QPushButton("Seçili Ölçümü Düzenle")
        configure_action(edit_button, label="Seçili ölçümü düzenle", role="secondary", tooltip="Kilitlenmemiş seçili ölçümün değerini düzenle")
        edit_button.clicked.connect(self._edit_selected)
        remove_button = QPushButton("Seçili Ölçümü Kaldır")
        configure_action(remove_button, label="Seçili ölçümü kaldır", role="danger", tooltip="Kilitlenmemiş seçili ölçümü kaldır")
        remove_button.clicked.connect(self._delete_selected)
        verify_button = QPushButton("Doğrula ve Kilitle")
        configure_action(verify_button, label="Ölçümü doğrula ve kilitle", role="primary", tooltip="Seçili ölçümü klinik kullanıcı onayıyla kilitle")
        verify_button.clicked.connect(self._verify_selected)
        evidence_button = QPushButton("Ölçüm Kanıtını Gör")
        configure_action(evidence_button, label="Ölçüm kanıtını gör", role="quiet", tooltip="Seçili ölçümün dört nokta ve provenance bilgisini görüntüle")
        evidence_button.clicked.connect(self._show_evidence)
        buttons.addStretch()
        buttons.addWidget(evidence_button)
        buttons.addWidget(edit_button)
        buttons.addWidget(remove_button)
        buttons.addWidget(verify_button)
        layout.addLayout(buttons)

    @staticmethod
    def _summary_text(rows: list[dict]) -> str:
        if not rows:
            return "Henüz kayıtlı Cobb ölçümü yok."

        pairs: dict[tuple[str, str, str], list[dict]] = {}
        unpaired = 0
        for row in rows:
            upper = str(row.get("upper_vertebra", "") or "").strip()
            lower = str(row.get("lower_vertebra", "") or "").strip()
            direction = str(row.get("curve_direction", "") or "").strip()
            if upper and lower:
                pairs.setdefault((upper, lower, direction), []).append(row)
            else:
                unpaired += 1

        parts = [f"Toplam {len(rows)} Cobb ölçümü."]
        for (upper, lower, direction), pair_rows in sorted(pairs.items()):
            chronological = sorted(
                pair_rows,
                key=lambda row: (
                    str(row.get("exam_date", "") or ""),
                    str(row.get("created_at", "") or ""),
                    int(row.get("id", 0) or 0),
                ),
            )
            first = float(chronological[0].get("angle_degrees", 0.0))
            latest = float(chronological[-1].get("angle_degrees", 0.0))
            delta = latest - first
            parts.append(
                f"{upper}–{lower}{(' | ' + direction) if direction and direction != 'Belirtilmedi' else ''}: "
                f"{len(pair_rows)} ölçüm, {first:.2f}° → {latest:.2f}° (Δ {delta:+.2f}°)."
            )

        if unpaired:
            parts.append(f"Vertebra bilgisi olmayan eski kayıt: {unpaired}.")
        return "  |  ".join(parts)

    def _delete_selected(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        answer = QMessageBox.question(
            self,
            "Cobb ölçümünü kaldır",
            "Seçili ölçüm kaydı silinecek. DICOM dosyası değişmeyecek.\n\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        measurement = self.rows[index]
        if bool(measurement.get("is_locked")):
            QMessageBox.information(self, "Cobb ölçümü", "Doğrulanıp kilitlenen ölçüm kaldırılamaz.")
            return
        try:
            self.repository.delete_cobb_measurement(int(measurement["id"]))
        except PermissionError as exc:
            QMessageBox.warning(self, "Cobb ölçümü", str(exc))
            return
        self.repository.record_audit_event(self.patient_id, "cobb_measurement_deleted", f"Kayıt #{measurement['id']}", actor=self.actor, actor_role=self.actor_role)
        self.accept()

    def _edit_selected(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        measurement = self.rows[index]
        if bool(measurement.get("is_locked")):
            QMessageBox.information(self, "Cobb ölçümü", "Doğrulanıp kilitlenen ölçüm değiştirilemez.")
            return
        angle, accepted = QInputDialog.getDouble(
            self, "Cobb ölçümünü düzenle", "Cobb açısı (derece):",
            float(measurement["angle_degrees"]), 0.0, 180.0, 2,
        )
        if not accepted:
            return
        try:
            self.repository.update_cobb_measurement(int(measurement["id"]), angle)
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(self, "Cobb ölçümü", str(exc))
            return
        self.repository.record_audit_event(self.patient_id, "cobb_measurement_updated", f"Kayıt #{measurement['id']}; {angle:.2f} derece", actor=self.actor, actor_role=self.actor_role)
        self.accept()

    def _verify_selected(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        if self.actor_role not in {"Yönetici", "Hekim"}:
            QMessageBox.warning(self, "Ölçüm doğrulama", "Cobb ölçümünü yalnızca Hekim veya Yönetici rolü doğrulayıp kilitleyebilir.")
            return
        measurement = self.rows[index]
        if bool(measurement.get("is_locked")):
            QMessageBox.information(self, "Ölçüm doğrulama", "Bu ölçüm zaten kilitli.")
            return
        note, accepted = QInputDialog.getMultiLineText(self, "Ölçüm doğrulama", "Doğrulama notu (isteğe bağlı):")
        if not accepted:
            return
        self.repository.verify_and_lock_cobb_measurement(int(measurement["id"]), self.actor or "Yerel Hekim", note)
        self.repository.record_audit_event(self.patient_id, "cobb_measurement_verified", f"Kayıt #{measurement['id']} doğrulandı ve kilitlendi", actor=self.actor, actor_role=self.actor_role)
        self.accept()

    def _show_evidence(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        measurement = self.rows[index]
        try:
            points = json.loads(str(measurement.get("point_data", "")))
        except (TypeError, ValueError, json.JSONDecodeError):
            points = []
        if points:
            point_text = "\n".join(
                f"{number}. X={float(point.get('x', 0)):.1f}, Y={float(point.get('y', 0)):.1f}"
                for number, point in enumerate(points, 1)
            )
        else:
            point_text = "Bu eski ölçüm kaydında nokta kanıtı bulunmuyor."
        message = (
            f"Ölçüm: {float(measurement.get('angle_degrees', 0)):.2f}°\n"
            f"Son vertebralar: {_pair_text(measurement)}\n"
            f"Eğri yönü: {_direction_text(measurement)}\n"
            f"Yöntem: {measurement.get('measurement_method', 'manual_4_point')}"
            f" (sürüm {measurement.get('measurement_version', '1')})\n"
            f"Oluşturan: {measurement.get('created_by', '') or '—'}\n"
            f"SOP Instance UID: {measurement.get('source_sop_instance_uid', '') or 'eski kayıt / yok'}\n\n"
            f"Dört noktalı ölçüm kanıtı:\n{point_text}\n\n"
            "Bu koordinatlar görüntü sahnesi koordinatlarıdır; orijinal DICOM dosyası değiştirilmez."
        )
        QMessageBox.information(self, "Cobb ölçüm kanıtı", message)
