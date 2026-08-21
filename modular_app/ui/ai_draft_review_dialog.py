from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ai.model_runtime import CobbSuggestion


class AICobbDraftReviewDialog(QDialog):
    """Small review gate: an AI draft is never persisted by this dialog itself."""

    APPROVER_ROLES = frozenset({"yönetici", "hekim", "administrator", "doctor", "admin"})
    EXPERT_ROLES = frozenset({"hekim", "doctor"})

    def __init__(self, suggestion: CobbSuggestion, reviewer: str, role: str, parent=None):
        super().__init__(parent)
        self.suggestion = suggestion
        self.reviewer = str(reviewer or "").strip()
        self.role = str(role or "").strip()
        self.decision = ""
        self.review_note = ""
        self.setWindowTitle("AI Cobb Taslağını İncele")
        self.setMinimumWidth(540)

        root = QVBoxLayout(self)
        title = QLabel("<b>AI ölçüm önerisini inceleyin</b>")
        title.setStyleSheet("font-size: 15px;")
        root.addWidget(title)

        warning = QLabel(
            "Bu sonuç yapay zekânın taslağıdır. Dört noktanın görüntü üzerindeki yerini kontrol edin. "
            "Onaylamadan hiçbir ölçüm kaydedilmez."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #f1c40f; padding: 8px; background: #3b3420; border-radius: 4px;")
        root.addWidget(warning)

        safety = suggestion.safety_status.replace("_", " ")
        details = QLabel(
            f"<b>Önerilen Cobb açısı:</b> {suggestion.angle_degrees:.2f}°<br>"
            f"<b>Model güveni:</b> {suggestion.confidence:.1%}<br>"
            f"<b>Model sürümü:</b> {suggestion.model_version}<br>"
            f"<b>Teknik kontrol:</b> {safety}<br>"
            f"<b>İnceleyen kullanıcı:</b> {self.reviewer or 'Belirlenmedi'} ({self.role or 'Rol yok'})"
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(details.textInteractionFlags())
        details.setStyleSheet("color: #f5f7fa; padding: 10px; background: #242424; border: 1px solid #444;")
        root.addWidget(details)

        note_label = QLabel("Onay notu veya ret nedeni:")
        root.addWidget(note_label)
        self.note_edit = QTextEdit()
        self.note_edit.setObjectName("ai_draft_review_note")
        self.note_edit.setPlaceholderText("Örnek: Üst ve alt son-plak noktaları görüntü üzerinde doğrulandı.")
        self.note_edit.setFixedHeight(88)
        root.addWidget(self.note_edit)

        self.permission_label = QLabel()
        self.permission_label.setWordWrap(True)
        root.addWidget(self.permission_label)

        action_row = QHBoxLayout()
        self.approve_button = QPushButton("Onayla ve Kaydet")
        self.approve_button.setObjectName("approve_ai_draft_button")
        self.approve_button.clicked.connect(self._approve)
        action_row.addWidget(self.approve_button)
        self.reject_button = QPushButton("Reddet (Kaydetme)")
        self.reject_button.setObjectName("reject_ai_draft_button")
        self.reject_button.clicked.connect(self._reject_draft)
        action_row.addWidget(self.reject_button)
        root.addLayout(action_row)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        close_box.rejected.connect(self.reject)
        root.addWidget(close_box)
        self._apply_permission_state()

    def _can_review(self) -> bool:
        required_roles = (
            self.EXPERT_ROLES
            if "expert_approval_required" in self.suggestion.safety_codes
            else self.APPROVER_ROLES
        )
        return self.role.casefold() in required_roles and bool(self.reviewer)

    def _apply_permission_state(self) -> None:
        allowed = self._can_review()
        self.approve_button.setEnabled(allowed)
        self.reject_button.setEnabled(allowed)
        if allowed:
            self.permission_label.setText("Bu işlem yalnızca onayınızdan sonra kalıcı ölçüm kaydı oluşturur.")
        else:
            if "expert_approval_required" in self.suggestion.safety_codes:
                self.permission_label.setText("Bu modelin taslağını yalnızca adı tanımlı Hekim rolündeki uzman onaylayabilir veya reddedebilir.")
            else:
                self.permission_label.setText(
                    "Bu taslağı yalnızca Yönetici veya Hekim rolündeki, adı tanımlı kullanıcılar onaylayabilir ya da reddedebilir."
                )
            self.permission_label.setStyleSheet("color: #f1c40f;")

    def _approve(self) -> None:
        if not self._can_review():
            return
        self.decision = "approved"
        self.review_note = self.note_edit.toPlainText().strip()
        self.accept()

    def _reject_draft(self) -> None:
        if not self._can_review():
            return
        note = self.note_edit.toPlainText().strip()
        if not note:
            QMessageBox.information(self, "AI taslağı", "Ret nedeni girin; ölçüm kaydedilmeyecektir.")
            return
        self.decision = "rejected"
        self.review_note = note
        self.accept()
