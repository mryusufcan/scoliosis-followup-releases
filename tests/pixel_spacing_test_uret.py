from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid


def add_cross(img, x, y, size=18, value=60000):
    h, w = img.shape
    x0, x1 = max(0, x - size), min(w - 1, x + size)
    y0, y1 = max(0, y - size), min(h - 1, y + size)
    img[y, x0:x1 + 1] = value
    img[y0:y1 + 1, x] = value


root = tk.Tk()
root.withdraw()

folder = filedialog.askdirectory(title="PixelSpacing test DICOM'unu kaydedeceğiniz klasörü seçin")
if not folder:
    raise SystemExit("Klasör seçilmedi.")

out = Path(folder) / "PixelSpacing_Test_0.5x0.8mm.dcm"

rows = 1000
cols = 1000
row_spacing = 0.5      # mm / pixel, vertical
column_spacing = 0.8   # mm / pixel, horizontal

img = np.zeros((rows, cols), dtype=np.uint16)

# Mild background pattern so the image is easy to see.
yy, xx = np.indices(img.shape)
img[:] = np.clip(4000 + (yy * 10) + (xx * 3), 0, 30000).astype(np.uint16)

# Horizontal 200 px pair: 200 * 0.8 mm = 160 mm = 16.00 cm
h1 = (300, 300)
h2 = (500, 300)

# Vertical 200 px pair: 200 * 0.5 mm = 100 mm = 10.00 cm
v1 = (700, 300)
v2 = (700, 500)

for p in (h1, h2, v1, v2):
    add_cross(img, *p)

# Draw guide lines.
img[h1[1], h1[0]:h2[0] + 1] = 50000
img[v1[1]:v2[1] + 1, v1[0]] = 50000

meta = FileMetaDataset()
meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
meta.MediaStorageSOPInstanceUID = generate_uid()
meta.TransferSyntaxUID = ExplicitVRLittleEndian
meta.ImplementationClassUID = generate_uid()

ds = FileDataset(str(out), {}, file_meta=meta, preamble=b"\0" * 128)
ds.SOPClassUID = SecondaryCaptureImageStorage
ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
ds.StudyInstanceUID = generate_uid()
ds.SeriesInstanceUID = generate_uid()
ds.PatientName = "PIXELSPACING^TEST"
ds.PatientID = "PIXEL-SPACING-001"
ds.StudyDate = "20260817"
ds.Modality = "OT"
ds.SeriesDescription = "PixelSpacing Measurement Validation"
ds.Rows = rows
ds.Columns = cols
ds.SamplesPerPixel = 1
ds.PhotometricInterpretation = "MONOCHROME2"
ds.BitsAllocated = 16
ds.BitsStored = 16
ds.HighBit = 15
ds.PixelRepresentation = 0
ds.PixelSpacing = [str(row_spacing), str(column_spacing)]
ds.WindowCenter = 16000
ds.WindowWidth = 32000
ds.PixelData = img.tobytes()
ds.save_as(str(out), enforce_file_format=True)

notes = Path(folder) / "PixelSpacing_Test_NOTLARI.txt"
notes.write_text(
    "PixelSpacing test DICOM\n"
    "=======================\n\n"
    "PixelSpacing = [0.5, 0.8] mm/pixel\n"
    "  Row spacing    = 0.5 mm/pixel (dikey)\n"
    "  Column spacing = 0.8 mm/pixel (yatay)\n\n"
    "TEST 1 - Yatay çizgi\n"
    "Sol ve sağ artı işaretinin merkezlerini ölçün.\n"
    "Piksel mesafesi: 200 px\n"
    "Beklenen: 200 * 0.8 = 160 mm = 16.00 cm\n\n"
    "TEST 2 - Dikey çizgi\n"
    "Üst ve alt artı işaretinin merkezlerini ölçün.\n"
    "Piksel mesafesi: 200 px\n"
    "Beklenen: 200 * 0.5 = 100 mm = 10.00 cm\n\n"
    "TEST 3 - 90 derece döndürme\n"
    "Görüntüyü 90 derece döndürüp aynı çizgileri tekrar ölçün.\n"
    "Fiziksel mesafe değişmemelidir.\n",
    encoding="utf-8"
)

messagebox.showinfo(
    "Hazır",
    f"Test DICOM oluşturuldu:\n{out}\n\n"
    "Yatay ölçüm beklenen: 16.00 cm\n"
    "Dikey ölçüm beklenen: 10.00 cm"
)
