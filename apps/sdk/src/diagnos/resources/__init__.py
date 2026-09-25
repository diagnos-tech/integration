"""🇺🇸 The resources a workspace exposes to a service account — patients, exams, drives.

🇧🇷 Os recursos que um workspace expõe a uma service account — pacientes, exames, drives.
"""

from __future__ import annotations

from .drives import Drive, Drives, UploadSource
from .exams import Exams
from .patients import Patients

__all__ = ["Drive", "Drives", "Exams", "Patients", "UploadSource"]
