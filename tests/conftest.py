"""Pytest oturumu boyunca tek ve önceden temalanmış Qt uygulaması tutar."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from main import apply_app_theme


# Modül düzeyindeki güçlü referans, test dosyaları arasında QApplication'ın
# Python sarmalayıcısının toplanmasını ve native Qt nesnesinin yenilenmesini
# engeller. Tema da herhangi bir test penceresi oluşmadan önce bir kez kurulur.
QT_TEST_APPLICATION = QApplication.instance() or QApplication([])
apply_app_theme(QT_TEST_APPLICATION, "dark")
