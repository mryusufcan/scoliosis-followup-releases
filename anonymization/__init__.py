"""Non-destructive DICOM de-identification helpers.

The source DICOM is always opened read-only and a new copy is written to a
user-selected folder.  This module deliberately does not claim that it can
remove annotations burned into image pixels.
"""

from .basic_dicom_anonymizer import AnonymizationError, anonymize_dicom_files

__all__ = ["AnonymizationError", "anonymize_dicom_files"]
