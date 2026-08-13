# Secondary Capture DICOM compatibility test plan

The application creates a new, derived Secondary Capture DICOM. Source DICOM files are never modified.

## Local automated checks

After dependency installation run:

```powershell
python tests\run_modular_tests.py
```

This validates synthetic DICOM files, project sample DICOM files, missing Pixel Data, multi-frame warnings, and whether a generated Secondary Capture can be reopened by `pydicom`.

## Viewer/PACS acceptance matrix

For each target environment, create an Overlay Secondary Capture in the application, then test these checks manually:

| Target | Required result |
|---|---|
| Local DICOM viewer | File opens; patient/study information is visible; image renders. |
| Orthanc or equivalent PACS | C-STORE succeeds; received instance is visible in the study. |
| Target production PACS | The site's PACS administrator verifies acceptance and presentation. |

Record viewer/PACS product, version, date, transfer result, and any warning in the application's `İşlem Geçmişi` or the local deployment record.

## Safety boundary

Successful file opening confirms technical interoperability only. It does not validate clinical interpretation, diagnostic accuracy, or workflow approval.
