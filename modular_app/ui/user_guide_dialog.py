from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


GUIDE_SECTIONS = (
    (
        "Hızlı Başlangıç",
        """
        <h2>Hızlı Başlangıç</h2>
        <ol>
          <li><b>Görüntüleyici</b> sekmesinde <b>Görüntü / DICOM Aç</b> ile dosya veya klasör seçin.</li>
          <li>Soldaki Hasta / Tetkik / Seri ağacından görüntüyü seçin.</li>
          <li>Tek görüntüyü incelemek için Görüntüleyici, parçaları birleştirmek için Görüntü Birleştirme,
              eski ve yeni tetkikleri karşılaştırmak için Skolyoz Takip sekmesini kullanın.</li>
          <li>Hasta geçmişi ve raporlar için üstteki <b>Hasta Takibi</b> menüsünü açın.</li>
        </ol>
        <p><b>Önemli:</b> Uygulama karar destek ve takip aracıdır. Ölçümler uzman hekim tarafından
        doğrulanmadan kesin klinik değerlendirme olarak kullanılmamalıdır.</p>
        """,
    ),
    (
        "Görüntüleyici",
        """
        <h2>Görüntüleyici</h2>
        <p>DICOM ve desteklenen normal görüntüleri tek ekranda incelemek için kullanılır.</p>
        <ol>
          <li><b>Görüntü / DICOM Aç</b> ile bir veya birden fazla dosya ya da klasör açın.</li>
          <li>Soldaki ağaç hasta → tetkik → seri → görüntü düzenindedir. Bir görüntüye tıklayarak açın.</li>
          <li><b>Görüntüyü Sığdır</b> görüntüyü çalışma alanına yeniden yerleştirir.</li>
          <li>Yakınlaştırma, kaydırma, pencere/seviye, döndürme ve çevirme araçları yalnızca görünümü değiştirir;
              kaynak DICOM dosyasını değiştirmez.</li>
          <li><b>Cobb Ölçümü</b> modunda üst son plak üzerinde iki, alt son plak üzerinde iki nokta seçin.
              Dördüncü noktadan sonra açı çizilir ve takip geçmişine kaydedilir.</li>
          <li>Omur etiketi modunda görüntüye tıklayın, omur seviyesini seçin; etiketler yerel veritabanında tutulur.</li>
        </ol>
        <p>Yanlış işlemde ölçüm/etiket yönetim ekranından taslak kaydı kaldırabilir veya görünümü sıfırlayabilirsiniz.
        Doğrulanıp kilitlenen ölçümler değiştirilemez.</p>
        """,
    ),
    (
        "Görüntü Birleştirme",
        """
        <h2>Görüntü Birleştirme</h2>
        <p>İki, üç veya dört ardışık çekimi tek uzun görüntüde birleştirir.</p>
        <ol>
          <li>Parçaları <b>Üst / Orta / Alt</b> sırasıyla yükleyin; gerekirse isteğe bağlı <b>4. Parça</b> alanını kullanın.</li>
          <li>Önizlemeleri kontrol edin. Yanlış parçayı <b>Kaldır</b> ile çıkarın.</li>
          <li>Gerekirse Manuel Nokta Modu ile örtüşen anatomik noktaları işaretleyin.</li>
          <li><b>Otomatik Hizalama</b> kenar korelasyonunu, <b>Pozlama Eşitleme</b> yalnızca görsel ton uyumunu sağlar.</li>
          <li><b>Hizala / Birleştir</b> ile sonuç üretin. Sonuç önizlemesinde parlaklık, kontrast ve yakınlaştırmayı kontrol edin.</li>
          <li><b>Kaydet (PNG + DICOM)</b> ile hem görüntü hem Secondary Capture DICOM çıktısı oluşturun.</li>
        </ol>
        <p>Kaydetmeden önce parça sırası, anatomik örtüşme ve hasta bilgilerinin aynı hastaya ait olduğunu doğrulayın.</p>
        """,
    ),
    (
        "Skolyoz Takip ve Mukayese",
        """
        <h2>Skolyoz Takip ve Mukayese</h2>
        <p>Aynı hastanın farklı tarihli tetkiklerini yan yana veya üst üste karşılaştırır.</p>
        <ol>
          <li>Soldaki ortak ağaçtan aynı hastaya ait iki farklı tetkik seçin.</li>
          <li><b>Yan Yana Mukayese</b> iki görüntüyü ayrı panellerde gösterir.</li>
          <li><b>Üst Üste (Overlay) Çakıştır</b> görüntüleri bindirir. X, Y, zoom ve saydamlık ayarlarıyla hizalayın.</li>
          <li><b>Overlay Sıfırla</b> hizalama ayarlarını başlangıca döndürür.</li>
          <li>Görünüm menüsünden hizalamayı kilitleyebilir, Blink modunu ve senkron görünümü açabilirsiniz.</li>
          <li>Uygun hizalamayı <b>Overlay Oturumunu Kaydet</b> ile saklayın veya Secondary Capture DICOM olarak dışa aktarın.</li>
        </ol>
        <p>Mukayese için iki farklı görüntü gerekir. Farklı hastalara ait görüntüler kullanılmamalıdır.</p>
        """,
    ),
    (
        "Hasta Takibi",
        """
        <h2>Hasta Takibi Menüsü</h2>
        <ul>
          <li><b>Hasta Kartı:</b> tanı, hekim, tedavi planı, sonraki kontrol ve yerel notlar.</li>
          <li><b>Görüntü Notları:</b> kaynak DICOM'u değiştirmeden görüntüye bağlı not tutar.</li>
          <li><b>Tetkik Geçmişi:</b> hastanın kayıtlı tetkiklerini listeler; seçilen geçmiş görüntüyü mukayeseye gönderir.</li>
          <li><b>Hasta Takip Özeti:</b> tetkik, ölçüm ve takip bilgilerinin toplu görünümüdür.</li>
          <li><b>Cobb Ölçüm Geçmişi / Trend Grafiği:</b> kayıtları ve zaman içindeki açı değişimini gösterir.</li>
          <li><b>Hasta Listesi ve Arama:</b> yerel veritabanındaki hastaları bulur.</li>
          <li><b>Yaklaşan / Gecikmiş Kontroller ve Takip Uyarıları:</b> hasta kartındaki kontrol tarihlerini izler.</li>
          <li><b>İşlem Geçmişi:</b> önemli kayıt, doğrulama ve dışa aktarma işlemlerini denetim kaydı olarak gösterir.</li>
          <li><b>Veri Kalite Kontrolü:</b> eksik veya tutarsız takip kayıtlarını bildirir.</li>
          <li><b>Yerel Kullanıcı ve Roller:</b> Yönetici, Hekim ve Görüntüleme Uzmanı yetkilerini yönetir.</li>
        </ul>
        """,
    ),
    (
        "Raporlama ve Dışa Aktarma",
        """
        <h2>Raporlama ve Dışa Aktarma</h2>
        <ul>
          <li><b>PDF takip raporu:</b> seçili hastanın takip özetini PDF olarak üretir.</li>
          <li><b>CSV dışa aktarımı:</b> takip verilerini tablo programlarında kullanılacak biçimde verir.</li>
          <li><b>Araştırma kopyası:</b> seçili DICOM'ların doğrudan hasta kimliklerini kaldırılmış kopyasını oluşturur.
              Çıktıyı paylaşmadan önce yine de kurumunuzun gizlilik sürecinden geçirin.</li>
          <li><b>Teknik kalite denetimi:</b> piksel verisi, boyut, aktarım sözdizimi ve çok kare durumunu kontrol eder.</li>
        </ul>
        <p>Dışa aktarma kaynak DICOM'ları silmez veya değiştirmez.</p>
        """,
    ),
    (
        "PACS",
        """
        <h2>PACS İşlemleri</h2>
        <p><b>Hasta Takibi → PACS Sorgula / Al / Gönder</b> yolundan açılır.</p>
        <ol>
          <li>Yerel AE Title, uzak PACS AE Title, sunucu adresi ve portu girin.</li>
          <li>Önce <b>Bağlantıyı Test Et</b> ile DICOM Echo doğrulaması yapın.</li>
          <li>C-FIND ile hasta/tetkik sorgulayın.</li>
          <li>Kurum PACS yapılandırmasına göre C-GET veya C-MOVE ile görüntü alın.</li>
          <li>C-STORE ile gönderilecek dosyaları mutlaka önceden teknik olarak doğrulayın.</li>
        </ol>
        <p>PACS bilgileri hastanenin PACS yöneticisinden alınır. Gerçek ortam doğrulaması yapılmadan üretim sistemine gönderim yapmayın.</p>
        """,
    ),
    (
        "Yapay Zekâ",
        """
        <h2>Yapay Zekâ Özellikleri</h2>
        <h3>Yerel AI Cobb Asistanı — Mazurowski modeli</h3>
        <p>Gelişmiş menüsündeki <b>Yerel AI Cobb Asistanı</b>, omurga maskesi ve merkez eğrisinden kayıt dışı bir Cobb taslağı üretir.
        Analiz uygulamayla birlikte gelen ONNX modeliyle tamamen yerel çalışır; Docker gerekmez ve görüntü bilgisayar dışına gönderilmez.</p>
        <ol>
          <li>AP/PA tam omurga DICOM görüntüsünü açın ve <b>Gelişmiş → Yerel AI Cobb Asistanı</b> yolunu seçin.</li>
          <li><b>Yerel Analizi Çalıştır</b> ile taslağı üretip <b>Taslağı Görüntüye Aktar</b> ile çizgileri inceleyin.</li>
          <li>Kayıt gerekiyorsa <b>Gelişmiş → AI Taslağını İncele / Onayla</b> yolunu açın. Yalnızca adı tanımlı Hekim veya Yönetici onaylayabilir.</li>
          <li>Onay verilmezse ölçüm geçmişine hiçbir kayıt yazılmaz; ret nedeni yalnızca denetim kaydına eklenir.</li>
        </ol>
        <p><b>Yapay Zekâ Cobb Asistanı</b> yalnızca uygun, bütünlüğü doğrulanmış yerel ONNX modeli kuruluysa çalışır.
        Sonuç ekrana <b>AI TASLAK</b> olarak çizilir; otomatik olarak klinik ölçüm kaydı oluşturmaz.</p>
        <h3>Deneysel AI 68-Landmark Taslağı</h3>
        <p>Bu özellik, 17 vertebra adayı için toplam 68 köşe landmarkını yalnızca görüntü üzerinde incelemek amacıyla üretir.
        İstenirse landmark geometrisinden deneysel bir Cobb adayı da hesaplar. <b>Tanı koymaz ve hiçbir sonucu otomatik ölçüm
        kaydına dönüştürmez.</b></p>
        <ol>
          <li>Tek kareli AP/PA DX veya CR DICOM görüntüsünü Görüntüleyicide açın.</li>
          <li>Üst menüden <b>Gelişmiş → Yerel AI Omurga Asistanı</b> yolunu açın.</li>
          <li>DICOM yön bilgisi boşsa görüntüyü inceleyip <b>AP</b> veya <b>PA kullanıcı doğrulaması</b> seçin. Bu seçim kaynak DICOM'u değiştirmez.</li>
          <li>Deneysel/kayıt dışı uyarıyı okuyun ve <b>Yerel Analizi Başlat</b> düğmesine basın.</li>
          <li>Teknik kontroller geçerse <b>Taslağı Görüntüye Aktar (Kaydetmez)</b> düğmesiyle turkuaz noktaları görüntü üzerinde inceleyin.</li>
          <li>Noktaları kontrol ettikten sonra isterseniz <b>Deneysel Cobb Taslağını Öner (Kaydetmez)</b> seçeneğini kullanın.</li>
          <li>En az 13 vertebra adayı eşiği geçerse kısmi önizleme açılır; düşük güvenli noktalar sarı gösterilir. AI Cobb görülebilir ancak düşük güvenli taslak olarak işaretlenir ve kaydedilemez.</li>
          <li>Daha düşük güvenli veya görüntü sınırı dışındaki sonuçlar gösterilmez. Noktalar otomatik düzeltilmez ya da kırpılmaz.</li>
        </ol>
        <p>AI Cobb adayı yalnızca görsel rehberdir ve onay/kayıt düğmesi kapalı tutulur. Klinik takip için normal manuel Cobb aracını
        kullanarak çizgileri kendiniz doğrulayın; landmark ve Cobb taslakları ölçüm geçmişine yazılmaz.
        V2 kabul/klinik doğrulama eksikleri, model paket denetiminde görünür kalır.</p>
        <p><b>AI Eğitim Verisi Hazırlama:</b></p>
        <ol>
          <li>Tek kareli DICOM'u Görüntüleyicide açın.</li>
          <li>Görünüm → AI Eğitim Verisi Hazırlama → Aktif Görüntüde 4 Nokta İşaretle seçin.</li>
          <li>Üst son plağı soldan sağa iki, alt son plağı soldan sağa iki noktayla işaretleyin.</li>
          <li>Modülü yeniden açın; Hekim/Yönetici doğru etiketi seçip doğrulasın ve kilitlesin.</li>
          <li>Hazır etiketleri dışa aktarın. Çıktı metadata içermeyen gri PNG ve normalize noktaları içerir.</li>
        </ol>
        <p>AI çıktısı uzman kontrolünün yerine geçmez. Hasta verisi uygulama tarafından bir bulut servisine gönderilmez.</p>
        """,
    ),
    (
        "Lisans, Güncelleme ve Güvenlik",
        """
        <h2>Lisans, Güncelleme ve Güvenlik</h2>
        <ul>
          <li><b>Lisans Yönetimi:</b> ad, e-posta ve lisans anahtarıyla cihaz lisansını etkinleştirir.</li>
          <li>İlk lisanssız deneme süresi 14 gündür. Etkin lisans için çevrimdışı tolerans en fazla 6 saattir; süreyi kapatıp açmak sıfırlamaz.</li>
          <li><b>Güncellemeleri Denetle:</b> imzalı güncelleme JSON adresinden yeni sürümü kontrol eder.</li>
          <li><b>Yerel Veri Durumu:</b> veritabanının okunabilirliğini denetler.</li>
          <li><b>Tanı Paketi:</b> destek amacıyla günlük ve teknik bilgileri toplar; hasta veritabanını pakete eklemez.</li>
          <li>Dağıtım bütünlüğü bozulursa uygulama çalışmayı reddeder. EXE klasöründeki dahili dosyaları değiştirmeyin.</li>
        </ul>
        """,
    ),
    (
        "İlk Kurulum Tercihleri",
        """
        <h2>İlk Kurulum Tercihleri</h2>
        <p>İlk kullanım sihirbazı yeni bir yerel kurulumda kullanıcı, rol, tema, başlangıç alanı ve isteğe bağlı PACS bilgilerini hazırlar.</p>
        <ul>
          <li>Tema daha sonra <b>Görüntüleme → Tema</b> menüsünden değiştirilebilir.</li>
          <li>Yerel kullanıcılar <b>Hasta Takibi → Yerel Kullanıcı ve Roller</b> ekranından yönetilebilir.</li>
          <li>PACS bilgileri PACS bağlantı ekranından güncellenip bağlantı testi yapılabilir.</li>
          <li>Sihirbazı yeniden çalıştırmak için <b>Yardım → İlk Kurulum Sihirbazını Yeniden Aç</b> yolunu kullanın.</li>
        </ul>
        """,
    ),
    (
        "Yedekleme ve Geri Dönüş",
        """
        <h2>Yedekleme ve Geri Dönüş</h2>
        <ul>
          <li><b>Şifreli Veritabanı Yedeği:</b> uygulama içindeki hasta takip kayıtlarını parola korumalı yedekler.</li>
          <li><b>Geri Yükle:</b> mevcut veritabanını seçilen şifreli yedekten geri getirir; işlemden önce ayrıca güncel yedek alın.</li>
          <li>Kaynak kod geliştirmesinde <b>restore point</b> arşivleri sürüme geri dönmek içindir; hasta verisi yedeğinin yerine geçmez.</li>
          <li>Kurulu uygulamanın kullanıcı verileri genellikle <code>%LOCALAPPDATA%\\ScoliosisFollowUp</code> klasöründedir.</li>
        </ul>
        """,
    ),
    (
        "Sık Karşılaşılan Durumlar",
        """
        <h2>Sık Karşılaşılan Durumlar</h2>
        <ul>
          <li><b>“Önce DICOM seçin”:</b> soldaki ağaçtan görüntü satırını seçin veya Görüntüleyicide DICOM açın.</li>
          <li><b>Mukayese başlamıyor:</b> aynı hastanın iki farklı görüntüsünü seçtiğinizden emin olun.</li>
          <li><b>Piksel verisi açılamıyor:</b> dosya bozuk, çok kareli veya desteklenmeyen sıkıştırmada olabilir; Teknik Kalite Denetimi çalıştırın.</li>
          <li><b>AI hazır değil:</b> doğrulanmış ONNX model ve manifest dosyaları henüz kurulmamıştır.</li>
          <li><b>PACS bağlantısı yok:</b> adres, port, AE Title, güvenlik duvarı ve PACS izinlerini kurum yöneticisiyle doğrulayın.</li>
          <li><b>Uygulama açılmıyor:</b> EXE klasörünün tamamının birlikte bulunduğunu kontrol edin; Help → Hata Günlüğü Konumu ile kayıtları inceleyin.</li>
        </ul>
        """,
    ),
)


class UserGuideDialog(QDialog):
    """Searchable, offline application manual bundled with the program."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nasıl Kullanılır? — Scoliosis Follow-Up")
        self.resize(1050, 700)

        root = QVBoxLayout(self)
        title = QLabel("<b>Scoliosis Follow-Up Kullanım Rehberi</b>")
        title.setStyleSheet("font-size:16px;")
        root.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rehberde ara… (ör. Cobb, PACS, yedekleme)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_sections)
        root.addWidget(self.search)

        content = QHBoxLayout()
        self.section_list = QListWidget()
        self.section_list.setMinimumWidth(260)
        self.section_list.setMaximumWidth(330)
        self.section_list.currentItemChanged.connect(self.show_section)
        content.addWidget(self.section_list)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("QTextBrowser { padding: 12px; }")
        content.addWidget(self.browser, 1)
        root.addLayout(content, 1)

        footer = QHBoxLayout()
        hint = QLabel("Rehber çevrimdışı çalışır ve uygulamayla birlikte paketlenir.")
        hint.setStyleSheet("color:#95a5a6;")
        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        footer.addWidget(hint)
        footer.addStretch()
        footer.addWidget(close)
        root.addLayout(footer)

        self.filter_sections("")

    def filter_sections(self, query: str):
        needle = str(query or "").strip().casefold()
        self.section_list.clear()
        for title, html in GUIDE_SECTIONS:
            searchable = f"{title} {html}".casefold()
            if needle and needle not in searchable:
                continue
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, html)
            self.section_list.addItem(item)
        if self.section_list.count():
            self.section_list.setCurrentRow(0)
        else:
            self.browser.setHtml("<h3>Sonuç bulunamadı</h3><p>Başka bir kelimeyle aramayı deneyin.</p>")

    def show_section(self, current, previous=None):
        if current is not None:
            self.browser.setHtml(str(current.data(Qt.ItemDataRole.UserRole) or ""))
