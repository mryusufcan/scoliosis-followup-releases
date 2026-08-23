from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


ONBOARDING_SCHEMA_VERSION = 1
SETTINGS_ORGANIZATION = "MRYusufCan"
SETTINGS_APPLICATION = "ScoliosisFollowUp"
PACS_SETTINGS_ORGANIZATION = "ScoliosisFollowUp"
PACS_SETTINGS_APPLICATION = "ScoliosisFollowUp"


def onboarding_settings() -> QSettings:
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def pacs_settings() -> QSettings:
    # Keep the legacy namespace so existing PACS configuration is preserved.
    return QSettings(PACS_SETTINGS_ORGANIZATION, PACS_SETTINGS_APPLICATION)


def onboarding_is_complete(settings: QSettings | None = None) -> bool:
    store = settings or onboarding_settings()
    try:
        return int(store.value("onboarding/schema_version", 0) or 0) >= ONBOARDING_SCHEMA_VERSION
    except (TypeError, ValueError):
        return False


def mark_onboarding_complete(settings: QSettings | None = None) -> None:
    store = settings or onboarding_settings()
    store.setValue("onboarding/schema_version", ONBOARDING_SCHEMA_VERSION)
    store.sync()


def should_show_onboarding(*, database_existed: bool, settings: QSettings | None = None) -> bool:
    """Show automatically only for a genuinely new local installation."""
    if onboarding_is_complete(settings):
        return False
    return not bool(database_existed)


@dataclass(frozen=True)
class FirstRunChoices:
    display_name: str
    role: str
    theme: str
    start_page: str
    configure_pacs: bool
    pacs_host: str = ""
    pacs_port: int = 104
    pacs_called_ae: str = ""
    pacs_calling_ae: str = "SCOLIOSIS_APP"
    open_guide: bool = False


class FirstRunWizard(QDialog):
    """Professional, offline first-use setup flow for the desktop application."""

    STEP_TITLES = (
        "Hoş geldiniz",
        "Kullanıcı ve rol",
        "Görünüm",
        "PACS (isteğe bağlı)",
        "Veri güvenliği",
        "Hazır",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İlk Kullanım Sihirbazı — Scoliosis Follow-Up")
        self.setModal(True)
        self.resize(920, 620)
        self.setMinimumSize(820, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        header = QFrame()
        header.setObjectName("wizardHeader")
        header_layout = QVBoxLayout(header)
        title = QLabel("Scoliosis Follow-Up")
        title.setFont(QFont(title.font().family(), 18, QFont.Weight.DemiBold))
        subtitle = QLabel("Güvenli ve kişiselleştirilmiş ilk kurulumu birkaç adımda tamamlayın.")
        subtitle.setObjectName("wizardMuted")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(24, 18, 24, 12)
        body.setSpacing(24)
        self.steps = QListWidget()
        self.steps.setObjectName("wizardSteps")
        self.steps.setFixedWidth(220)
        self.steps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.steps.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for index, text in enumerate(self.STEP_TITLES, start=1):
            self.steps.addItem(f"{index}.  {text}")
        body.addWidget(self.steps)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._welcome_page())
        self.pages.addWidget(self._user_page())
        self.pages.addWidget(self._appearance_page())
        self.pages.addWidget(self._pacs_page())
        self.pages.addWidget(self._security_page())
        self.pages.addWidget(self._finish_page())
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(24, 10, 24, 20)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("wizardMuted")
        self.back_button = QPushButton("Geri")
        self.next_button = QPushButton("İleri")
        self.next_button.setDefault(True)
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        footer.addWidget(self.progress_label)
        footer.addStretch()
        footer.addWidget(self.back_button)
        footer.addWidget(self.next_button)
        root.addLayout(footer)

        self.configure_pacs.toggled.connect(self._toggle_pacs_fields)
        self.pages.currentChanged.connect(self._refresh_navigation)
        self._toggle_pacs_fields(False)
        self._refresh_navigation(0)

        self.setStyleSheet("""
            QFrame#wizardHeader { background: palette(alternate-base); border-bottom: 1px solid palette(mid); }
            QFrame#wizardHeader QLabel { padding-left: 16px; }
            QLabel#wizardMuted { color: palette(mid); }
            QListWidget#wizardSteps { background: transparent; border: none; font-size: 14px; }
            QListWidget#wizardSteps::item { padding: 11px 8px; border-radius: 6px; }
            QListWidget#wizardSteps::item:selected { background: palette(highlight); color: palette(highlighted-text); }
            QLabel#wizardPageTitle { font-size: 20px; font-weight: 600; }
        """)

    @staticmethod
    def _page(title: str, intro: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setObjectName("wizardPageTitle")
        description = QLabel(intro)
        description.setWordWrap(True)
        description.setObjectName("wizardMuted")
        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addSpacing(14)
        return page, layout

    def _welcome_page(self) -> QWidget:
        page, layout = self._page(
            "Hoş geldiniz",
            "Bu sihirbaz yalnızca ilk kullanımda temel tercihlerinizi hazırlar. Seçimleri daha sonra uygulama menülerinden değiştirebilirsiniz.",
        )
        note = QLabel(
            "<b>Klinik güvenlik</b><br><br>Uygulama DICOM görüntüleme, Cobb ölçümü ve longitudinal takip için yardımcı araçlar sunar. "
            "Otomatik veya AI sonuçları uzman değerlendirmesinin ve klinik kararın yerine geçmez."
        )
        note.setWordWrap(True)
        note.setFrameStyle(QFrame.Shape.StyledPanel)
        note.setMargin(18)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _user_page(self) -> QWidget:
        page, layout = self._page("Kullanıcı ve rol", "Denetim kayıtlarında görünecek yerel kullanıcıyı belirleyin.")
        form = QFormLayout()
        self.display_name = QLineEdit("Yerel Yönetici")
        self.display_name.setMaxLength(80)
        self.role = QComboBox()
        self.role.addItem("Yönetici", "Yönetici")
        self.role.addItem("Hekim", "Hekim")
        self.role.addItem("Görüntüleme Uzmanı", "Teknisyen")
        form.addRow("Görünen ad", self.display_name)
        form.addRow("Rol", self.role)
        layout.addLayout(form)
        hint = QLabel("Yerel kullanıcı ve rol seçimi kurumsal oturum açma sisteminin yerine geçmez.")
        hint.setWordWrap(True)
        hint.setObjectName("wizardMuted")
        layout.addWidget(hint)
        layout.addStretch()
        return page

    def _appearance_page(self) -> QWidget:
        page, layout = self._page("Görünüm ve başlangıç", "Uygulamanın görünümünü ve açılışta gösterilecek çalışma alanını seçin.")
        form = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItem("Koyu tema", "dark")
        self.theme.addItem("Açık tema", "light")
        self.start_page = QComboBox()
        self.start_page.addItem("Görüntüleyici", "viewer")
        self.start_page.addItem("Takip ve Karşılaştırma", "workspace")
        self.start_page.addItem("Görüntü Birleştirme", "stitcher")
        form.addRow("Tema", self.theme)
        form.addRow("Başlangıç alanı", self.start_page)
        layout.addLayout(form)
        layout.addStretch()
        return page

    def _pacs_page(self) -> QWidget:
        page, layout = self._page("PACS bağlantısı", "Kurum PACS bilgilerini şimdi kaydedebilir veya bu adımı daha sonra tamamlayabilirsiniz.")
        self.configure_pacs = QCheckBox("PACS bağlantısını şimdi yapılandır")
        layout.addWidget(self.configure_pacs)
        form = QFormLayout()
        existing = pacs_settings()
        self.pacs_host = QLineEdit(str(existing.value("pacs/host", "") or ""))
        self.pacs_port = QSpinBox()
        self.pacs_port.setRange(1, 65535)
        self.pacs_port.setValue(int(existing.value("pacs/port", 104) or 104))
        self.pacs_called = QLineEdit(str(existing.value("pacs/called_ae", "") or ""))
        self.pacs_calling = QLineEdit(str(existing.value("pacs/calling_ae", "SCOLIOSIS_APP") or "SCOLIOSIS_APP"))
        self._pacs_inputs = (self.pacs_host, self.pacs_port, self.pacs_called, self.pacs_calling)
        form.addRow("PACS IP / sunucu", self.pacs_host)
        form.addRow("Port", self.pacs_port)
        form.addRow("Called AE Title", self.pacs_called)
        form.addRow("Calling AE Title", self.pacs_calling)
        layout.addLayout(form)
        hint = QLabel("Bu adım ağ bağlantısı kurmaz. Bağlantıyı daha sonra PACS ekranındaki “Bağlantıyı Test Et” düğmesiyle doğrulayın.")
        hint.setWordWrap(True)
        hint.setObjectName("wizardMuted")
        layout.addWidget(hint)
        layout.addStretch()
        return page

    def _security_page(self) -> QWidget:
        page, layout = self._page("Veri güvenliği", "Yerel hasta verilerinin korunması için aşağıdaki çalışma modelini gözden geçirin.")
        text = QLabel(
            "• Hasta takip verileri bu Windows kullanıcısının yerel uygulama klasöründe tutulur.\n\n"
            "• Kaynak DICOM dosyaları görüntüleme ve ölçüm sırasında değiştirilmez.\n\n"
            "• Düzenli olarak şifreli veritabanı yedeği oluşturmanız önerilir.\n\n"
            "• Araştırma veya destek için veri paylaşmadan önce anonimleştirme sürecini uygulayın."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch()
        return page

    def _finish_page(self) -> QWidget:
        page, layout = self._page("Kurulum hazır", "Seçimleriniz kaydedilecek ve ana çalışma alanı açılacak.")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setFrameStyle(QFrame.Shape.StyledPanel)
        self.summary.setMargin(18)
        self.open_guide = QCheckBox("Ana pencere açılınca kısa kullanım rehberini göster")
        layout.addWidget(self.summary)
        layout.addWidget(self.open_guide)
        layout.addStretch()
        return page

    def _toggle_pacs_fields(self, enabled: bool) -> None:
        for widget in self._pacs_inputs:
            widget.setEnabled(bool(enabled))

    def _validate_page(self, index: int) -> bool:
        if index == 1 and not self.display_name.text().strip():
            QMessageBox.warning(self, "Kullanıcı", "Görünen ad boş bırakılamaz.")
            self.display_name.setFocus()
            return False
        if index == 3 and self.configure_pacs.isChecked():
            if not all((self.pacs_host.text().strip(), self.pacs_called.text().strip(), self.pacs_calling.text().strip())):
                QMessageBox.warning(self, "PACS", "PACS sunucusu, Called AE Title ve Calling AE Title zorunludur.")
                return False
            if len(self.pacs_called.text().strip()) > 16 or len(self.pacs_calling.text().strip()) > 16:
                QMessageBox.warning(self, "PACS", "AE Title alanları en fazla 16 karakter olabilir.")
                return False
        return True

    def _back(self) -> None:
        self.pages.setCurrentIndex(max(0, self.pages.currentIndex() - 1))

    def _next(self) -> None:
        index = self.pages.currentIndex()
        if not self._validate_page(index):
            return
        if index == self.pages.count() - 1:
            self.accept()
            return
        if index == self.pages.count() - 2:
            self._update_summary()
        self.pages.setCurrentIndex(index + 1)

    def _refresh_navigation(self, index: int) -> None:
        self.steps.setCurrentRow(index)
        self.progress_label.setText(f"Adım {index + 1} / {self.pages.count()}")
        self.back_button.setEnabled(index > 0)
        self.next_button.setText("Kurulumu Tamamla" if index == self.pages.count() - 1 else "İleri")

    def _update_summary(self) -> None:
        pacs_line = "Yapılandırılacak" if self.configure_pacs.isChecked() else "Daha sonra"
        self.summary.setText(
            f"<b>Kullanıcı:</b> {self.display_name.text().strip()} — {self.role.currentText()}<br><br>"
            f"<b>Tema:</b> {self.theme.currentText()}<br>"
            f"<b>Başlangıç alanı:</b> {self.start_page.currentText()}<br>"
            f"<b>PACS:</b> {pacs_line}"
        )

    def choices(self) -> FirstRunChoices:
        return FirstRunChoices(
            display_name=self.display_name.text().strip(),
            role=str(self.role.currentData()),
            theme=str(self.theme.currentData()),
            start_page=str(self.start_page.currentData()),
            configure_pacs=self.configure_pacs.isChecked(),
            pacs_host=self.pacs_host.text().strip(),
            pacs_port=self.pacs_port.value(),
            pacs_called_ae=self.pacs_called.text().strip(),
            pacs_calling_ae=self.pacs_calling.text().strip(),
            open_guide=self.open_guide.isChecked(),
        )


def save_pacs_choices(choices: FirstRunChoices) -> None:
    if not choices.configure_pacs:
        return
    store = pacs_settings()
    store.setValue("pacs/host", choices.pacs_host)
    store.setValue("pacs/port", choices.pacs_port)
    store.setValue("pacs/called_ae", choices.pacs_called_ae)
    store.setValue("pacs/calling_ae", choices.pacs_calling_ae)
    store.sync()
