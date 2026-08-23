from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def find_project_root() -> Path:
    """Script tools/ altında veya proje kökünde olsa da gerçek proje kökünü bul."""
    here = Path(__file__).resolve().parent

    candidates = [here, *here.parents]
    for candidate in candidates:
        if (candidate / "main.py").is_file() and (candidate / "VERSION").is_file():
            return candidate

    raise RuntimeError(
        "Proje kökü bulunamadı. main.py ve VERSION aynı proje klasöründe olmalı."
    )


ROOT = find_project_root()


def repair_console_text(value: str) -> str:
    """UTF-8'in cp1252/cp1254 olarak yanlış yorumlanmasından doğan mojibake'i düzelt."""
    if not value:
        return value

    # En sık görülen belirtiler:
    # BaÄŸÄ±mlÄ±lÄ±k, baÅŸarÄ±lÄ±, gÃ¼ncelleme, DaÄŸÄ±tÄ±m, vb.
    markers = ("Ã", "Ä", "Å", "Â", "â€", "ï»¿")
    if not any(marker in value for marker in markers):
        return value

    candidates = [value]

    # Windows Bat/PowerShell zincirinde en sık cp1252/cp1254 üzerinden bozuluyor.
    for encoding in ("cp1252", "cp1254"):
        try:
            fixed = value.encode(encoding).decode("utf-8")
            candidates.append(fixed)
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    # Daha az mojibake işareti içeren sonucu seç.
    def score(s: str) -> int:
        bad = ("Ã", "Ä", "Å", "Â", "â€", "ï»¿", "�")
        return sum(s.count(x) for x in bad)

    return min(candidates, key=score)


@dataclass(frozen=True)
class ToolAction:
    title: str
    description: str
    kind: str
    target: str
    accent: str = "blue"
    requires_confirm: bool = False


ACTIONS = {
    "development": [
        ToolAction("Uygulamayı Başlat", "Ana uygulamayı normal modda çalıştır.", "python", "main.py", "green"),
        ToolAction("Otomatik Testler", "Güncel pytest test paketinin tamamını çalıştır.", "python_args", "-m pytest -q", "blue"),
        ToolAction("Debug Başlat", "Uygulamayı konsol çıktısıyla çalıştır.", "bat_or_python", "scripts/dev/Uygulamayi_Hata_Gostererek_Baslat.bat|main.py", "blue"),
        ToolAction("Python Ortamı", "Python, PySide6 ve pydicom sürümlerini göster.", "environment", "", "gray"),
    ],
    "license": [
        ToolAction("Lisans Yönetimi", "Yönetici lisans panelini aç.", "bat", "scripts/admin/Lisans_Yonetimi_Ac.bat", "purple"),
        ToolAction("Lisans Durumunu Kontrol Et", "Bu bilgisayarın aktif lisans durumunu RPC üzerinden kontrol et.", "python", "scripts/dev/Lisans_RPC_Kontrol.py", "blue"),
        ToolAction("Trial Simülasyonu", "Yerel kayıtlar silinmiş gibi taze kurulum denemesi yap.", "python", "scripts/dev/Trial_Taze_Kurulum_Simulasyonu.py", "orange"),
        ToolAction("Lisans Policy Testleri", "Lisans ve trial politikası unit testlerini çalıştır.", "python_args", "-m unittest tests.test_license_policy", "blue"),
    ],
    "release": [
        ToolAction("Hızlı Deneme EXE", "Geliştirme amaçlı hızlı EXE paketi oluştur.", "bat", "scripts/build/Hizli_Deneme_EXE_Olustur.bat", "blue"),
        ToolAction("Tam Sürüm + Installer", "Tam dağıtım paketini ve installer'ı oluştur.", "bat", "scripts/build/Tam_Surum_Olustur.bat", "orange", True),
        ToolAction("Update JSON Oluştur", "Güncelleme bildirim dosyasını yeniden üret.", "bat", "scripts/release/Guncelleme_JSON_Olustur.bat", "blue"),
        ToolAction("Yayın Paketini Doğrula", "Mevcut release paketini kabul testinden geçir.", "bat", "scripts/release/Yayin_Paketini_Dogrula.bat", "green"),
        ToolAction("Dağıtım Güvenlik Denetimi", "Secret/admin dosyası/paketleme güvenliği kontrollerini çalıştır.", "python", "scripts/release/Dagitim_Guvenlik_Denetimi.py", "purple"),
        ToolAction("Tek Tık Yayın Paketi", "Test → build → installer → update → yerel doğrulama zincirini çalıştır ve yüklemeye hazır paketi oluştur.", "python", "scripts/release/Tek_Tik_Yayin.py", "orange", True),
        ToolAction("GitHub'a Yayımla", "Hazır paketi ayrıntılı sürüm notlarıyla GitHub Releases'a yükle; README ve Pages'i güncelle ve uzaktan doğrula.", "python_args", "scripts/release/GitHub_Yayinla.py --yes", "red", True),
    ],
    "files": [
        ToolAction("Kök Klasörü Sadeleştir", "Teknik kaynakları Windows Gezgini'nde gizle; ana araç, belgeler ve dağıtım/arşiv çıktıları görünür kalsın.", "python_args", "scripts/maintenance/project_root_visibility.py --hide", "purple", True),
        ToolAction("Teknik Dosyaları Göster", "Sade görünümü geri al ve gizlenen teknik proje öğelerini yeniden görünür yap.", "python_args", "scripts/maintenance/project_root_visibility.py --show", "gray"),
        ToolAction("Güvenli Proje ZIP'i", "Kaynak kodu paylaşılabilir ZIP olarak paketle; özel anahtarları, DICOM/hasta verilerini ve derleme çıktılarını dışarıda bırakıp ZIP'i doğrula.", "python", "scripts/maintenance/project_archive.py", "green"),
        ToolAction("Temizlik Önizlemesi", "Silmeden önce yalnızca yeniden üretilebilir build/cache hedeflerini ve yaklaşık boyutlarını göster.", "python", "scripts/maintenance/safe_generated_cleanup.py", "blue"),
        ToolAction("Güvenli Temizliği Uygula", "Yalnızca build, pytest cache, __pycache__ ve bytecode kalıntılarını kaldır; sürüm, hasta verileri, arşivler ve sanal ortamlar korunur.", "python_args", "scripts/maintenance/safe_generated_cleanup.py --apply", "orange", True),
        ToolAction("Proje ZIP'leri", "Merkezden oluşturulan güvenli kaynak ZIP'lerini aç.", "folder", "project_archives", "gray"),
        ToolAction("Proje Klasörü", "Projenin ana klasörünü Explorer'da aç.", "folder", ".", "gray"),
        ToolAction("Dist", "Derlenmiş uygulama çıktılarını aç.", "folder", "dist", "gray"),
        ToolAction("Installer", "Installer çıktılarını aç.", "folder", "installer", "gray"),
        ToolAction("Releases", "Hazır sürüm paketlerini aç.", "folder", "releases", "gray"),
        ToolAction(
            "Restore Oluştur",
            "Mevcut proje kaynaklarının güvenli anlık kopyasını .restore_points içine oluştur.",
            "restore_create",
            "",
            "green",
            True,
        ),
        ToolAction("Restore Points", "Refactor ve işlem yedeklerini aç.", "folder", ".restore_points", "gray"),
        ToolAction(
            "Restore Retention Dry-Run",
            "Son 7 gün ve en yeni 10 restore point'i koruyarak eski küçük kopyaları raporla; varsayılan olarak hiçbir dosyayı silmez.",
            "bat",
            "scripts/maintenance/Restore_Point_Retention.bat",
            "gray",
        ),
        ToolAction("Proje Rehberi", "HTML proje rehberini varsayılan tarayıcıda aç.", "file", "docs/Proje_Rehberi.html", "blue"),
        ToolAction("Kullanıcı Verileri / Loglar", "LOCALAPPDATA altındaki uygulama verilerini aç.", "userdata", "", "gray"),
    ],
}

# Günlük kullanılan işlemler ana ekranda tek yerde tutulur. Diğer sayfalar
# daha seyrek kullanılan teknik ve yönetim araçlarına ayrılır.
def _action_named(section: str, title: str) -> ToolAction:
    return next(action for action in ACTIONS[section] if action.title == title)


QUICK_ACTIONS = [
    _action_named("development", "Uygulamayı Başlat"),
    _action_named("development", "Otomatik Testler"),
    _action_named("files", "Güvenli Proje ZIP'i"),
    _action_named("release", "Tam Sürüm + Installer"),
    _action_named("files", "Restore Oluştur"),
]

_QUICK_TITLES = {action.title for action in QUICK_ACTIONS}
for _section in ("development", "release", "files"):
    ACTIONS[_section] = [
        action for action in ACTIONS[_section] if action.title not in _QUICK_TITLES
    ]


class ActionCard(QFrame):
    requested = Signal(object)

    ACCENTS = {
        "blue": ("#2563eb", "#1d4ed8"),
        "green": ("#16a34a", "#15803d"),
        "orange": ("#d97706", "#b45309"),
        "purple": ("#7c3aed", "#6d28d9"),
        "red": ("#dc2626", "#b91c1c"),
        "gray": ("#475569", "#334155"),
    }

    def __init__(self, action: ToolAction, parent=None):
        super().__init__(parent)
        self.action = action
        self.setObjectName("ActionCard")
        self.setMinimumHeight(145)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title = QLabel(action.title)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)

        desc = QLabel(action.description)
        desc.setObjectName("CardDescription")
        desc.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addStretch()

        button = QPushButton("Çalıştır")
        button.setCursor(Qt.PointingHandCursor)
        c1, c2 = self.ACCENTS.get(action.accent, self.ACCENTS["blue"])
        button.setStyleSheet(
            f"""
            QPushButton {{
                background:{c1};
                color:white;
                border:none;
                border-radius:7px;
                padding:8px 14px;
                font-weight:600;
            }}
            QPushButton:hover {{ background:{c2}; }}
            QPushButton:disabled {{ background:#3f4651; color:#8b949e; }}
            """
        )
        button.clicked.connect(lambda: self.requested.emit(self.action))
        self.button = button
        layout.addWidget(button)


class StatusCard(QFrame):
    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(4)

        caption = QLabel(title)
        caption.setObjectName("StatusCaption")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatusValue")
        self.value_label.setWordWrap(True)

        layout.addWidget(caption)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class ProjectControlCenter(QMainWindow):
    NAV_ITEMS = [
        ("Genel Bakış", "dashboard"),
        ("Gelişmiş Araçlar", "development"),
        ("Lisans / Trial", "license"),
        ("Sürüm Yönetimi", "versioning"),
        ("Yayın / Paketleme", "release"),
        ("Proje Araçları", "files"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scoliosis Follow-Up — Proje Kontrol Merkezi")
        self.resize(1280, 800)
        self.setMinimumSize(1050, 680)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.running_action: ToolAction | None = None

        # Sürüm değiştirme işlemi test başarısız olursa geri alınabilsin.
        self._pending_version_transaction = None

        self._build_ui()
        self._apply_style()
        self.refresh_status()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 20, 16, 16)
        side_layout.setSpacing(10)

        brand = QLabel("SCOLIOSIS\nFOLLOW-UP")
        brand.setObjectName("Brand")
        side_layout.addWidget(brand)

        subtitle = QLabel("Proje Kontrol Merkezi")
        subtitle.setObjectName("BrandSubtitle")
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(14)

        self.nav = QListWidget()
        self.nav.setObjectName("Navigation")
        self.nav.setSpacing(4)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for title, _key in self.NAV_ITEMS:
            item = QListWidgetItem(title)
            item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint()))
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._nav_changed)
        side_layout.addWidget(self.nav, 1)

        root_hint = QLabel(str(ROOT))
        root_hint.setObjectName("RootHint")
        root_hint.setWordWrap(True)
        side_layout.addWidget(root_hint)

        root_layout.addWidget(sidebar)

        # Main
        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(14)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        self.page_title = QLabel("Genel Bakış")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel("Proje durumu, lisans ve yayın araçları.")
        self.page_subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_subtitle)
        top.addLayout(title_box)
        top.addStretch()

        refresh_btn = QPushButton("Durumu Yenile")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self.refresh_status)
        top.addWidget(refresh_btn)

        main_layout.addLayout(top)

        # Status cards
        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status_version = StatusCard("Uygulama Sürümü", "—")
        self.status_feed = StatusCard("Update JSON", "—")
        self.status_license = StatusCard("Lisans", "Kontrol edilmedi")
        self.status_tests = StatusCard("Son Test", "Henüz çalıştırılmadı")
        for card in (self.status_version, self.status_feed, self.status_license, self.status_tests):
            status_row.addWidget(card, 1)
        main_layout.addLayout(status_row)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        self.stack = QStackedWidget()
        splitter.addWidget(self.stack)

        self.pages = {}
        self.pages["dashboard"] = self._make_dashboard()
        self.pages["development"] = self._make_action_page("Gelişmiş Geliştirme Araçları", ACTIONS["development"])
        self.pages["license"] = self._make_action_page("Lisans / Trial", ACTIONS["license"])
        self.pages["versioning"] = self._make_version_page()
        self.pages["release"] = self._make_action_page("Yayın / Paketleme", ACTIONS["release"])
        self.pages["files"] = self._make_action_page("Dosyalar / Yönetim", ACTIONS["files"])
        for _, key in self.NAV_ITEMS:
            self.stack.addWidget(self.pages[key])

        console_box = QFrame()
        console_box.setObjectName("ConsoleBox")
        console_layout = QVBoxLayout(console_box)
        console_layout.setContentsMargins(12, 10, 12, 10)
        console_layout.setSpacing(7)

        console_header = QHBoxLayout()
        console_title = QLabel("Canlı Komut Çıktısı")
        console_title.setObjectName("ConsoleTitle")
        console_header.addWidget(console_title)
        console_header.addStretch()

        self.stop_btn = QPushButton("Durdur")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_process)
        console_header.addWidget(self.stop_btn)

        clear_btn = QPushButton("Temizle")
        clear_btn.setObjectName("SecondaryButton")
        clear_btn.clicked.connect(lambda: self.console.clear())
        console_header.addWidget(clear_btn)

        console_layout.addLayout(console_header)

        self.console = QTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Cascadia Mono", 9))
        self.console.setPlaceholderText("Çalıştırılan komutların çıktısı burada görünecek...")
        console_layout.addWidget(self.console)

        input_row = QHBoxLayout()
        self.process_input = QLineEdit()
        self.process_input.setObjectName("ProcessInput")
        self.process_input.setPlaceholderText(
            "Komut bir yanıt bekliyorsa buraya yazın. Boş Enter göndermek için kutuyu boş bırakıp Enter'a basın."
        )
        self.process_input.setEnabled(False)
        self.process_input.returnPressed.connect(self.send_process_input)
        input_row.addWidget(self.process_input, 1)

        self.send_input_btn = QPushButton("Gönder")
        self.send_input_btn.setObjectName("PrimaryButton")
        self.send_input_btn.setEnabled(False)
        self.send_input_btn.clicked.connect(self.send_process_input)
        input_row.addWidget(self.send_input_btn)

        console_layout.addLayout(input_row)

        splitter.addWidget(console_box)
        splitter.setSizes([470, 220])

        main_layout.addWidget(splitter, 1)
        root_layout.addWidget(main, 1)

        self.nav.setCurrentRow(0)

    def _make_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info = QFrame()
        info.setObjectName("Hero")
        il = QVBoxLayout(info)
        il.setContentsMargins(20, 18, 20, 18)
        h = QLabel("En sık kullandığınız beş işlem burada.")
        h.setObjectName("HeroTitle")
        h.setWordWrap(True)
        p = QLabel(
            "Uygulamayı başlatabilir, testleri çalıştırabilir, güvenli ZIP veya restore "
            "oluşturabilir ve dağıtım paketini hazırlayabilirsiniz. Diğer seçenekler "
            "soldaki gelişmiş bölümlerde bulunur."
        )
        p.setObjectName("HeroText")
        p.setWordWrap(True)
        il.addWidget(h)
        il.addWidget(p)
        layout.addWidget(info)

        quick_title = QLabel("Hızlı İşlemler")
        quick_title.setObjectName("SectionTitle")
        layout.addWidget(quick_title)

        grid = QGridLayout()
        grid.setSpacing(10)
        for i, action in enumerate(QUICK_ACTIONS):
            card = ActionCard(action)
            card.requested.connect(self.run_action)
            grid.addWidget(card, i // 3, i % 3)
        layout.addLayout(grid)
        layout.addStretch()
        return self._wrap_scroll(page)

    def _make_version_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        heading = QLabel("Sürüm Yönetimi")
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)

        panel = QFrame()
        panel.setObjectName("Hero")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(20, 18, 20, 18)
        pl.setSpacing(12)

        current_row = QHBoxLayout()
        current_row.addWidget(QLabel("Mevcut sürüm:"))
        self.version_current_label = QLabel("—")
        self.version_current_label.setObjectName("StatusValue")
        current_row.addWidget(self.version_current_label)
        current_row.addStretch()
        pl.addLayout(current_row)

        new_row = QHBoxLayout()
        new_row.addWidget(QLabel("Yeni sürüm:"))
        self.version_input = QLineEdit()
        self.version_input.setObjectName("ProcessInput")
        self.version_input.setPlaceholderText("Örn: 1.5.2")
        self.version_input.setMaximumWidth(220)
        new_row.addWidget(self.version_input)

        patch_btn = QPushButton("Patch +1")
        patch_btn.setObjectName("SecondaryButton")
        patch_btn.clicked.connect(lambda: self.suggest_version("patch"))
        new_row.addWidget(patch_btn)

        minor_btn = QPushButton("Minor +1")
        minor_btn.setObjectName("SecondaryButton")
        minor_btn.clicked.connect(lambda: self.suggest_version("minor"))
        new_row.addWidget(minor_btn)

        major_btn = QPushButton("Major +1")
        major_btn.setObjectName("SecondaryButton")
        major_btn.clicked.connect(lambda: self.suggest_version("major"))
        new_row.addWidget(major_btn)

        new_row.addStretch()
        pl.addLayout(new_row)

        note = QLabel(
            "Yeni sürüm hazırlanırken VERSION ve update.json birlikte güncellenir. "
            "Ardından tüm testler çalıştırılır. Test başarısız olursa her iki dosya da "
            "otomatik olarak eski haline döndürülür."
        )
        note.setObjectName("HeroText")
        note.setWordWrap(True)
        pl.addWidget(note)

        action_row = QHBoxLayout()

        sync_btn = QPushButton("Sürüm Senkronunu Kontrol Et")
        sync_btn.setObjectName("SecondaryButton")
        sync_btn.clicked.connect(self.check_version_sync)
        action_row.addWidget(sync_btn)

        self.prepare_version_btn = QPushButton("Yeni Sürümü Hazırla")
        self.prepare_version_btn.setObjectName("PrimaryButton")
        self.prepare_version_btn.clicked.connect(self.prepare_new_version)
        action_row.addWidget(self.prepare_version_btn)

        action_row.addStretch()
        pl.addLayout(action_row)

        layout.addWidget(panel)

        flow = QFrame()
        flow.setObjectName("ActionCard")
        fl = QVBoxLayout(flow)
        fl.setContentsMargins(18, 16, 18, 16)

        flow_title = QLabel("Önerilen yayın akışı")
        flow_title.setObjectName("CardTitle")
        fl.addWidget(flow_title)

        flow_text = QLabel(
            "1. Patch / Minor / Major seç\n"
            "2. Yeni Sürümü Hazırla\n"
            "3. Otomatik testlerin geçmesini bekle\n"
            "4. Yayın / Paketleme → Tek Tık Tam Yayın\n"
            "5. Release paketini doğrula"
        )
        flow_text.setObjectName("CardDescription")
        flow_text.setWordWrap(True)
        fl.addWidget(flow_text)

        layout.addWidget(flow)
        layout.addStretch()

        return self._wrap_scroll(page)

    def _current_version_text(self) -> str:
        path = ROOT / "VERSION"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8-sig").strip()

    def _parse_semver(self, value: str):
        parts = value.strip().split(".")
        if len(parts) != 3:
            return None
        try:
            nums = tuple(int(part) for part in parts)
        except ValueError:
            return None
        if any(num < 0 for num in nums):
            return None
        return nums

    def suggest_version(self, kind: str):
        current = self._parse_semver(self._current_version_text())
        if current is None:
            QMessageBox.warning(
                self,
                "Sürüm okunamadı",
                "VERSION dosyası x.y.z biçiminde değil."
            )
            return

        major, minor, patch = current
        if kind == "patch":
            patch += 1
        elif kind == "minor":
            minor += 1
            patch = 0
        elif kind == "major":
            major += 1
            minor = 0
            patch = 0

        self.version_input.setText(f"{major}.{minor}.{patch}")

    def check_version_sync(self):
        version = self._current_version_text()
        update_path = ROOT / "update.json"

        if not version:
            QMessageBox.warning(self, "Sürüm", "VERSION dosyası okunamadı.")
            return

        if not update_path.exists():
            QMessageBox.warning(self, "Sürüm", "update.json bulunamadı.")
            return

        try:
            data = json.loads(update_path.read_text(encoding="utf-8-sig"))
            feed_version = str(data.get("version", "")).strip()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Sürüm",
                f"update.json okunamadı:\n{exc}"
            )
            return

        if version == feed_version:
            QMessageBox.information(
                self,
                "Sürüm Senkronu",
                f"VERSION ve update.json eşleşiyor:\n\n{version}"
            )
        else:
            QMessageBox.warning(
                self,
                "Sürüm Senkronu",
                f"Eşleşme yok.\n\nVERSION: {version}\nupdate.json: {feed_version}"
            )

    def prepare_new_version(self):
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.information(
                self,
                "İşlem devam ediyor",
                "Önce çalışan işlemin tamamlanmasını bekleyin."
            )
            return

        new_version = self.version_input.text().strip()
        parsed = self._parse_semver(new_version)
        if parsed is None:
            QMessageBox.warning(
                self,
                "Geçersiz sürüm",
                "Yeni sürüm x.y.z biçiminde olmalı. Örn: 1.5.2"
            )
            return

        old_version = self._current_version_text()
        if not old_version:
            QMessageBox.warning(self, "Sürüm", "VERSION dosyası okunamadı.")
            return

        if new_version == old_version:
            QMessageBox.information(
                self,
                "Sürüm",
                "Yeni sürüm mevcut sürümle aynı."
            )
            return

        answer = QMessageBox.question(
            self,
            "Yeni sürümü hazırla",
            (
                f"Mevcut sürüm: {old_version}\n"
                f"Yeni sürüm: {new_version}\n\n"
                "VERSION ve update.json güncellenecek ve ardından tüm testler "
                "çalıştırılacak. Test başarısız olursa otomatik geri alınacak.\n\n"
                "Devam edilsin mi?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        version_path = ROOT / "VERSION"
        update_path = ROOT / "update.json"

        try:
            old_version_bytes = version_path.read_bytes()
            old_update_bytes = update_path.read_bytes() if update_path.exists() else None

            version_path.write_text(new_version + "\n", encoding="utf-8")

            if update_path.exists():
                data = json.loads(update_path.read_text(encoding="utf-8-sig"))
                data["version"] = new_version
                update_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

            self._pending_version_transaction = {
                "old_version": old_version,
                "new_version": new_version,
                "version_bytes": old_version_bytes,
                "update_bytes": old_update_bytes,
            }

            self._append_console(
                f"\n>>> YENİ SÜRÜM HAZIRLANIYOR\n"
                f"VERSION: {old_version} -> {new_version}\n"
                f"update.json: {'güncellendi' if update_path.exists() else 'yok'}\n"
                "Otomatik testler başlatılıyor...\n"
            )

            self.prepare_version_btn.setEnabled(False)

            action = ToolAction(
                "Sürüm Hazırlama Testleri",
                f"{new_version} sürümü için tüm testler",
                "python_args",
                "-m pytest -q",
                "blue",
            )
            self._start_process(
                self.python_executable(),
                ["-m", "pytest", "-q"],
                action,
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Sürüm güncellenemedi",
                str(exc)
            )
            self._rollback_version_transaction()

    def _rollback_version_transaction(self):
        tx = self._pending_version_transaction
        if not tx:
            return

        try:
            (ROOT / "VERSION").write_bytes(tx["version_bytes"])
            update_bytes = tx.get("update_bytes")
            if update_bytes is not None:
                (ROOT / "update.json").write_bytes(update_bytes)
        finally:
            self._pending_version_transaction = None
            if hasattr(self, "prepare_version_btn"):
                self.prepare_version_btn.setEnabled(True)
            self.refresh_status()
            if hasattr(self, "version_current_label"):
                self.version_current_label.setText(self._current_version_text())

    def _make_action_page(self, title: str, actions: list[ToolAction]):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)

        grid = QGridLayout()
        grid.setSpacing(10)
        cols = 3
        for i, action in enumerate(actions):
            card = ActionCard(action)
            card.requested.connect(self.run_action)
            grid.addWidget(card, i // cols, i % cols)
        layout.addLayout(grid)
        layout.addStretch()
        return self._wrap_scroll(content)

    def _wrap_scroll(self, widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(widget)
        return scroll

    def _nav_changed(self, row: int):
        if row < 0:
            return
        title, key = self.NAV_ITEMS[row]
        self.page_title.setText(title)
        subtitles = {
            "dashboard": "Günlük kullanılan işlemler ve proje durumu.",
            "development": "Debug ve geliştirme ortamı gibi seyrek kullanılan teknik araçlar.",
            "license": "Lisans yönetimi, cihaz doğrulama ve trial kontrolleri.",
            "versioning": "VERSION ve update.json dosyalarını güvenli biçimde birlikte yönetin.",
            "release": "Build, installer, update.json, kabul ve güvenlik denetimleri.",
            "files": "Güvenli ZIP, temizlik, restore noktaları ve tüm proje klasörleri tek yerde.",
        }
        self.page_subtitle.setText(subtitles[key])
        self.stack.setCurrentWidget(self.pages[key])

    def python_executable(self) -> str:
        for environment in (".venv", ".venv-build"):
            venv = ROOT / environment / "Scripts" / "python.exe"
            if venv.exists():
                return str(venv)
        return sys.executable or "python"

    def refresh_status(self):
        version_file = ROOT / "VERSION"
        version = version_file.read_text(encoding="utf-8-sig").strip() if version_file.exists() else "Bulunamadı"
        self.status_version.set_value(version)
        if hasattr(self, "version_current_label"):
            self.version_current_label.setText(version)

        update_file = ROOT / "update.json"
        feed_version = "Bulunamadı"
        if update_file.exists():
            try:
                data = json.loads(update_file.read_text(encoding="utf-8-sig"))
                feed_version = str(data.get("version", "Sürüm alanı yok"))
            except Exception:
                feed_version = "Okunamadı"
        self.status_feed.set_value(feed_version)

        # Lisans durumunu ayrı bir QProcess ile bloklamadan çek.
        if self.process.state() == QProcess.NotRunning:
            script = ROOT / "scripts" / "dev" / "Lisans_RPC_Kontrol.py"
            if script.exists():
                self.status_license.set_value("Kontrol ediliyor…")
                self._start_process(
                    self.python_executable(),
                    [str(script)],
                    action=None,
                    silent_status=True,
                )

    def run_action(self, action: ToolAction):
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "İşlem devam ediyor", "Önce çalışan işlemin tamamlanmasını veya durdurulmasını bekleyin.")
            return

        if action.requires_confirm:
            answer = QMessageBox.question(
                self,
                "İşlemi onayla",
                f"{action.title}\n\n{action.description}\n\nDevam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        self.running_action = action
        self._append_console(f"\n>>> {action.title}\n{action.description}\n")

        kind = action.kind
        target = action.target

        if kind == "restore_create":
            try:
                restore_root = ROOT / ".restore_points"
                restore_root.mkdir(parents=True, exist_ok=True)

                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                version = self._current_version_text() or "unknown"
                safe_version = "".join(
                    ch for ch in version if ch.isalnum() or ch in "._-"
                ) or "unknown"
                snapshot = restore_root / f"manual_{stamp}_v{safe_version}"

                # Restore noktası kaynak kodu ve proje yapılandırmasını korur.
                # Büyük/üretilmiş klasörler ve gizli anahtarlar kopyalanmaz.
                excluded_dirs = {
                    ".restore_points",
                    ".venv-build",
                    ".git",
                    "__pycache__",
                    "dist",
                    "build",
                    "installer",
                    "releases",
                    "artifacts",
                    "node_modules",
                    "security_keys",
                }
                excluded_suffixes = {
                    ".pyc", ".pyo", ".log", ".tmp", ".dcm", ".dicom"
                }

                copied_files = 0
                copied_bytes = 0

                for source in ROOT.rglob("*"):
                    try:
                        rel = source.relative_to(ROOT)
                    except ValueError:
                        continue

                    if any(part in excluded_dirs for part in rel.parts):
                        continue
                    if source.is_dir():
                        continue
                    if source.suffix.lower() in excluded_suffixes:
                        continue

                    # Çok büyük çalışma/veri dosyalarını restore noktasına alma.
                    try:
                        size = source.stat().st_size
                    except OSError:
                        continue
                    if size > 50 * 1024 * 1024:
                        continue

                    target = snapshot / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    copied_files += 1
                    copied_bytes += size

                manifest = snapshot / "RESTORE_INFO.txt"
                manifest.write_text(
                    "\n".join(
                        [
                            "Scoliosis Follow-Up Restore Point",
                            "================================",
                            f"Oluşturma: {datetime.now().isoformat(timespec='seconds')}",
                            f"Sürüm: {version}",
                            f"Kaynak: {ROOT}",
                            f"Dosya sayısı: {copied_files}",
                            f"Toplam boyut: {copied_bytes / 1024 / 1024:.1f} MB",
                            "",
                            "Hariç tutulan ana alanlar:",
                            ", ".join(sorted(excluded_dirs)),
                            "",
                            "Not: security_keys, build/release çıktıları, DICOM ve büyük veri "
                            "dosyaları bu restore noktasına dahil edilmez.",
                        ]
                    ) + "\n",
                    encoding="utf-8",
                )

                self._append_console(
                    f"[RESTORE] Oluşturuldu: {snapshot}\n"
                    f"[RESTORE] {copied_files} dosya · "
                    f"{copied_bytes / 1024 / 1024:.1f} MB\n"
                )
                QMessageBox.information(
                    self,
                    "Restore oluşturuldu",
                    (
                        "Proje restore noktası başarıyla oluşturuldu.\n\n"
                        f"{snapshot}\n\n"
                        f"{copied_files} dosya · "
                        f"{copied_bytes / 1024 / 1024:.1f} MB"
                    ),
                )
            except Exception as exc:
                self._append_console(f"[HATA] Restore oluşturulamadı: {exc}\n")
                QMessageBox.critical(
                    self,
                    "Restore oluşturulamadı",
                    str(exc),
                )
            finally:
                self.running_action = None
            return

        if kind == "folder":
            path = (ROOT / target).resolve()
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
            self._append_console(f"[AÇILDI] {path}\n")
            self.running_action = None
            return

        if kind == "file":
            path = (ROOT / target).resolve()
            if not path.exists():
                # common legacy filename fallback
                alt = ROOT / "docs" / "Proje Rehberi.html"
                if alt.exists():
                    path = alt
            if not path.exists():
                self._append_console(f"[HATA] Dosya bulunamadı: {path}\n")
                self.running_action = None
                return
            os.startfile(str(path))
            self._append_console(f"[AÇILDI] {path}\n")
            self.running_action = None
            return

        if kind == "userdata":
            base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            path = base / "ScoliosisFollowUp"
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
            self._append_console(f"[AÇILDI] {path}\n")
            self.running_action = None
            return

        if kind == "environment":
            code = (
                "import sys; "
                "print('Python:', sys.version); "
                "print('Executable:', sys.executable); "
                "import PySide6, pydicom; "
                "print('PySide6:', PySide6.__version__); "
                "print('pydicom:', pydicom.__version__)"
            )
            self._start_process(self.python_executable(), ["-c", code], action)
            return

        if kind == "python":
            path = (ROOT / target).resolve()
            if not path.exists():
                self._missing(path)
                return
            self._start_process(self.python_executable(), [str(path)], action)
            return

        if kind == "python_args":
            self._start_process(self.python_executable(), target.split(), action)
            return

        if kind == "bat":
            path = (ROOT / target).resolve()
            if not path.exists():
                self._missing(path)
                return

            # BAT dosyasını doğrudan CALL ile çalıştır.
            # Release/build BAT'ları kendi içinde chcp 65001 uyguluyor.
            self._start_process(
                "cmd.exe",
                ["/d", "/c", "call", str(path)],
                action,
            )
            return

        if kind == "bat_or_python":
            bat_rel, py_rel = target.split("|", 1)
            bat_path = ROOT / bat_rel
            if bat_path.exists():
                self._start_process(
                    "cmd.exe",
                    ["/d", "/c", "call", str(bat_path)],
                    action,
                )
            else:
                py_path = ROOT / py_rel
                self._start_process(self.python_executable(), [str(py_path)], action)
            return

        self._append_console(f"[HATA] Bilinmeyen işlem türü: {kind}\n")
        self.running_action = None

    def _missing(self, path: Path):
        self._append_console(f"[HATA] Araç bulunamadı: {path}\n")
        QMessageBox.warning(self, "Araç bulunamadı", f"Dosya bulunamadı:\n{path}")
        self.running_action = None

    def _start_process(self, program: str, arguments: list[str], action: ToolAction | None, silent_status: bool = False):
        self.running_action = action
        self._silent_status = silent_status
        self.process.setWorkingDirectory(str(ROOT))

        # Alt klasordeki Python scriptleri (scripts/dev vb.) proje kokundeki
        # license_app.py ve diger ortak modulleri gorebilsin.
        env = QProcessEnvironment.systemEnvironment()
        existing_pythonpath = env.value("PYTHONPATH", "")
        root_path = str(ROOT)
        if existing_pythonpath:
            env.insert("PYTHONPATH", root_path + os.pathsep + existing_pythonpath)
        else:
            env.insert("PYTHONPATH", root_path)

        # Python alt süreçlerinde Türkçe/Unicode çıktıyı zorla UTF-8 yap.
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(env)

        self.process.start(program, arguments)
        if not self.process.waitForStarted(2500):
            self._append_console(f"[HATA] İşlem başlatılamadı: {program}\n")
            if action:
                QMessageBox.warning(self, "Başlatılamadı", f"{action.title} başlatılamadı.")
            self.running_action = None
            return
        self.stop_btn.setEnabled(True)
        self.process_input.setEnabled(True)
        self.send_input_btn.setEnabled(True)
        if not silent_status:
            self._append_console(f"$ {program} {' '.join(arguments)}\n[CWD] {ROOT}\n")
            self.process_input.setFocus()

    def _read_process_output(self):
        raw = bytes(self.process.readAllStandardOutput())

        # Windows batch / Python çıktıları farklı kodlamalarla gelebilir.
        # Önce UTF-8 dene; başarısızsa Türkçe Windows code page fallback uygula.
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp1254")
            except UnicodeDecodeError:
                text = raw.decode("cp850", errors="replace")

        text = repair_console_text(text)
        if not getattr(self, "_silent_status", False):
            self._append_console(text)
        else:
            # License RPC output parser
            low = text.lower()
            if "active" in low and "true" in low:
                self.status_license.set_value("Aktif")
            elif "active" in low and "false" in low:
                self.status_license.set_value("Aktif lisans yok")
            elif "etkin lisans doğrulandı" in low:
                self.status_license.set_value("Aktif")

    def _process_finished(self, exit_code: int, exit_status):
        self.stop_btn.setEnabled(False)
        self.process_input.setEnabled(False)
        self.send_input_btn.setEnabled(False)
        self.process_input.clear()

        action = self.running_action
        silent = getattr(self, "_silent_status", False)

        if silent:
            if self.status_license.value_label.text() == "Kontrol ediliyor…":
                self.status_license.set_value("Kontrol edilemedi" if exit_code else "Durum alındı")
        else:
            if exit_code == 0:
                self._append_console("\n[OK] İşlem başarıyla tamamlandı.\n")
            else:
                self._append_console(f"\n[HATA] İşlem çıkış kodu: {exit_code}\n")

            if action and action.title == "Otomatik Testler":
                self.status_tests.set_value("Başarılı" if exit_code == 0 else "Başarısız")
            if action and action.title == "Lisans Durumunu Kontrol Et":
                # output parser may already have set the value
                if self.status_license.value_label.text() in {"Kontrol edilmedi", "Kontrol ediliyor…"}:
                    self.status_license.set_value("Kontrol edildi" if exit_code == 0 else "Hata")

        # Sürüm hazırlama testlerinin sonucu.
        if action and action.title == "Sürüm Hazırlama Testleri":
            tx = self._pending_version_transaction
            if tx:
                if exit_code == 0:
                    new_version = tx["new_version"]
                    self._pending_version_transaction = None
                    if hasattr(self, "prepare_version_btn"):
                        self.prepare_version_btn.setEnabled(True)
                    self.refresh_status()
                    if hasattr(self, "version_current_label"):
                        self.version_current_label.setText(new_version)
                    self._append_console(
                        f"\n[SÜRÜM HAZIR] {new_version}\n"
                        "VERSION ve update.json güncel. Testler başarılı.\n"
                        "Şimdi Tek Tık Tam Yayın çalıştırabilirsiniz.\n"
                    )
                    QMessageBox.information(
                        self,
                        "Sürüm hazır",
                        (
                            f"{new_version} sürümü hazırlandı.\n\n"
                            "VERSION ve update.json güncel.\n"
                            "Otomatik testler başarılı.\n\n"
                            "Sonraki adım: Tek Tık Tam Yayın."
                        ),
                    )
                else:
                    old_version = tx["old_version"]
                    self._rollback_version_transaction()
                    self._append_console(
                        f"\n[GERİ ALINDI] Test başarısız olduğu için sürüm "
                        f"{old_version} değerine döndürüldü.\n"
                    )
                    QMessageBox.warning(
                        self,
                        "Sürüm geri alındı",
                        (
                            "Otomatik testler başarısız oldu.\n\n"
                            f"VERSION ve update.json tekrar {old_version} "
                            "sürümüne döndürüldü."
                        ),
                    )

        self.running_action = None
        self._silent_status = False

    def _process_error(self, error):
        if not getattr(self, "_silent_status", False):
            self._append_console(f"\n[QProcess HATASI] {error}\n")
        self.stop_btn.setEnabled(False)
        self.process_input.setEnabled(False)
        self.send_input_btn.setEnabled(False)

    def send_process_input(self):
        """Canli komutun stdin'ine bir satir gonder."""
        if self.process.state() == QProcess.NotRunning:
            return

        value = self.process_input.text()
        payload = (value + "\r\n").encode("utf-8")

        written = self.process.write(payload)
        if written == -1:
            self._append_console("\n[HATA] Komuta yanit gonderilemedi.\n")
            return

        # Kullanici ne gonderdigini konsolda da gorebilsin.
        display = value if value else "<ENTER>"
        self._append_console(f"\n> {display}\n")
        self.process_input.clear()
        self.process_input.setFocus()

    def stop_process(self):
        if self.process.state() == QProcess.NotRunning:
            return
        self._append_console("\n[DURDURULUYOR] İşlem sonlandırılıyor...\n")
        self.process.kill()

    def _append_console(self, text: str):
        self.console.moveCursor(QTextCursor.End)
        self.console.insertPlainText(text)
        self.console.ensureCursorVisible()

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background:#0f1115;
                color:#e6edf3;
                font-family:"Segoe UI";
                font-size:10pt;
            }
            #Sidebar {
                background:#161b22;
                border-right:1px solid #2b313a;
            }
            #Brand {
                color:#58a6ff;
                font-size:18px;
                font-weight:800;
                letter-spacing:1px;
            }
            #BrandSubtitle {
                color:#8b949e;
                font-size:11px;
            }
            #RootHint {
                color:#6e7681;
                font-size:9px;
                padding:8px;
                background:#0d1117;
                border-radius:6px;
            }
            #Navigation {
                background:transparent;
                border:none;
                outline:none;
            }
            #Navigation::item {
                padding:10px 12px;
                margin:2px 0;
                border-radius:7px;
                color:#c9d1d9;
            }
            #Navigation::item:selected {
                background:#1f6feb;
                color:white;
                font-weight:600;
            }
            #Navigation::item:hover:!selected {
                background:#21262d;
            }
            #PageTitle {
                font-size:23px;
                font-weight:700;
                color:#f0f6fc;
            }
            #PageSubtitle {
                color:#8b949e;
                font-size:10pt;
            }
            #StatusCard, #ActionCard, #Hero, #ConsoleBox {
                background:#161b22;
                border:1px solid #30363d;
                border-radius:10px;
            }
            #StatusCaption {
                color:#8b949e;
                font-size:9pt;
            }
            #StatusValue {
                color:#f0f6fc;
                font-size:15px;
                font-weight:700;
            }
            #CardTitle {
                color:#f0f6fc;
                font-size:13px;
                font-weight:700;
            }
            #CardDescription, #HeroText {
                color:#9da7b3;
                font-size:9.5pt;
            }
            #Hero {
                background:#111827;
                border:1px solid #25344a;
            }
            #HeroTitle {
                color:#dbeafe;
                font-size:15px;
                font-weight:700;
            }
            #SectionTitle {
                font-size:15px;
                font-weight:700;
                color:#f0f6fc;
                padding:4px 0;
            }
            #ConsoleTitle {
                font-weight:700;
                color:#c9d1d9;
            }
            #Console {
                background:#090c10;
                color:#b7f7c1;
                border:1px solid #252b33;
                border-radius:7px;
                padding:8px;
                selection-background-color:#264f78;
            }
            #ProcessInput {
                background:#0d1117;
                color:#f0f6fc;
                border:1px solid #30363d;
                border-radius:6px;
                padding:8px 10px;
                selection-background-color:#264f78;
            }
            #ProcessInput:focus {
                border:1px solid #58a6ff;
            }
            #ProcessInput:disabled {
                color:#6e7681;
                background:#11151a;
            }
            #PrimaryButton {
                background:#1f6feb;
                color:white;
                border:none;
                border-radius:6px;
                padding:8px 16px;
                font-weight:600;
            }
            #PrimaryButton:hover {
                background:#388bfd;
            }
            #PrimaryButton:disabled {
                background:#2d333b;
                color:#6e7681;
            }
            #SecondaryButton {
                background:#21262d;
                color:#c9d1d9;
                border:1px solid #30363d;
                border-radius:6px;
                padding:7px 12px;
            }
            #SecondaryButton:hover {
                background:#30363d;
            }
            #DangerButton {
                background:#7f1d1d;
                color:white;
                border:none;
                border-radius:6px;
                padding:7px 12px;
            }
            #DangerButton:hover {
                background:#991b1b;
            }
            #DangerButton:disabled {
                background:#2d333b;
                color:#6e7681;
            }
            QScrollArea {
                border:none;
                background:transparent;
            }
            QScrollBar:vertical {
                background:#11151a;
                width:10px;
                margin:0;
            }
            QScrollBar::handle:vertical {
                background:#30363d;
                min-height:28px;
                border-radius:5px;
            }
            QSplitter::handle {
                background:#20252d;
                height:2px;
            }
            """
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Scoliosis Follow-Up Project Control Center")
    win = ProjectControlCenter()
    if "--page" in sys.argv:
        try:
            page = sys.argv[sys.argv.index("--page") + 1]
            row = next(index for index, (_, key) in enumerate(win.NAV_ITEMS) if key == page)
            win.nav.setCurrentRow(row)
        except (IndexError, StopIteration):
            pass
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
