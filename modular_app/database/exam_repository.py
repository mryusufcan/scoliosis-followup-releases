from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


class ExamRepository:
    """SQLite repository for scoliosis exam history.

    This module is independent from the viewer/checkpoint application.
    """

    def __init__(self, db_path: str | Path = "data/scoliosis.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        # Yerel, tek-kullanıcılı uygulamada bu ayarlar küçük ama sık yapılan
        # timeline/audit kayıtlarını daha akıcı tutar. Kalıcı veri şeması veya
        # DICOM dosyaları üzerinde değişiklik yapmaz.
        con.execute("PRAGMA busy_timeout = 3000")
        con.execute("PRAGMA temp_store = MEMORY")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def initialize(self) -> None:
        with self.connection() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS exams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    patient_name TEXT,
                    exam_date TEXT NOT NULL,
                    body_part TEXT,
                    modality TEXT,
                    study_description TEXT,
                    dicom_path TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(patient_id, exam_date, dicom_path)
                )
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_exams_patient_date
                ON exams(patient_id, exam_date DESC)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_exams_patient_path
                ON exams(patient_id, dicom_path)
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS comparison_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    reference_path TEXT NOT NULL,
                    comparison_path TEXT NOT NULL,
                    overlay_offset_x REAL NOT NULL,
                    overlay_offset_y REAL NOT NULL,
                    overlay_scale REAL NOT NULL,
                    overlay_opacity REAL NOT NULL,
                    overlay_rotation REAL NOT NULL DEFAULT 0,
                    reference_window_center REAL,
                    reference_window_width REAL,
                    comparison_window_center REAL,
                    comparison_window_width REAL,
                    alignment_score REAL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            session_columns = {row[1] for row in con.execute("PRAGMA table_info(comparison_sessions)")}
            for name, definition in {
                "notes": "TEXT NOT NULL DEFAULT ''",
                "overlay_rotation": "REAL NOT NULL DEFAULT 0",
                "reference_window_center": "REAL",
                "reference_window_width": "REAL",
                "comparison_window_center": "REAL",
                "comparison_window_width": "REAL",
                "alignment_score": "REAL",
            }.items():
                if name not in session_columns:
                    con.execute(f"ALTER TABLE comparison_sessions ADD COLUMN {name} {definition}")
            con.execute("""
                CREATE TABLE IF NOT EXISTS cobb_measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    dicom_path TEXT NOT NULL,
                    exam_date TEXT NOT NULL DEFAULT '',
                    side TEXT NOT NULL,
                    angle_degrees REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Existing databases were created before exam_date was introduced.
            columns = {row[1] for row in con.execute("PRAGMA table_info(cobb_measurements)")}
            if "exam_date" not in columns:
                con.execute("ALTER TABLE cobb_measurements ADD COLUMN exam_date TEXT NOT NULL DEFAULT ''")
                con.execute(
                    """UPDATE cobb_measurements
                       SET exam_date = replace(substr(created_at, 1, 10), '-', '')
                       WHERE exam_date = ''"""
                )
            for name, definition in {
                "is_locked": "INTEGER NOT NULL DEFAULT 0",
                "verified_by": "TEXT NOT NULL DEFAULT ''",
                "verified_at": "TEXT",
                "verification_note": "TEXT NOT NULL DEFAULT ''",
                # Ölçüm değerinin yanında, dört noktalı manuel ölçümün
                # kaynak kanıtı da saklanır. DICOM piksel verisine veya
                # dosyasına hiçbir zaman yazılmaz.
                "source_sop_instance_uid": "TEXT NOT NULL DEFAULT ''",
                "point_data": "TEXT NOT NULL DEFAULT ''",
                "measurement_method": "TEXT NOT NULL DEFAULT 'manual_4_point'",
                "measurement_version": "TEXT NOT NULL DEFAULT '1'",
                "created_by": "TEXT NOT NULL DEFAULT ''",
                "provenance_json": "TEXT NOT NULL DEFAULT ''",
                "upper_vertebra": "TEXT NOT NULL DEFAULT ''",
                "lower_vertebra": "TEXT NOT NULL DEFAULT ''",
                "curve_direction": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if name not in columns:
                    con.execute(f"ALTER TABLE cobb_measurements ADD COLUMN {name} {definition}")
            con.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    actor TEXT NOT NULL DEFAULT '',
                    actor_role TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            audit_columns = {row[1] for row in con.execute("PRAGMA table_info(audit_events)")}
            for name, definition in {
                "actor": "TEXT NOT NULL DEFAULT ''",
                "actor_role": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if name not in audit_columns:
                    con.execute(f"ALTER TABLE audit_events ADD COLUMN {name} {definition}")
            con.execute("""
                CREATE TABLE IF NOT EXISTS patient_display_names (
                    patient_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS patient_profiles (
                    patient_id TEXT PRIMARY KEY,
                    diagnosis TEXT NOT NULL DEFAULT '',
                    referring_physician TEXT NOT NULL DEFAULT '',
                    treatment_plan TEXT NOT NULL DEFAULT '',
                    next_follow_up_date TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    updated_by TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS vertebra_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    dicom_path TEXT NOT NULL,
                    vertebra TEXT NOT NULL,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS image_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    dicom_path TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS app_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_name TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL CHECK(role IN ('Yönetici', 'Hekim', 'Teknisyen')),
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute(
                "INSERT OR IGNORE INTO app_users(display_name, role) VALUES (?, ?)",
                ("Yerel Yönetici", "Yönetici"),
            )
            user_columns = {row[1] for row in con.execute("PRAGMA table_info(app_users)")}
            for name, definition in {
                "password_salt": "TEXT NOT NULL DEFAULT ''",
                "password_hash": "TEXT NOT NULL DEFAULT ''",
                "password_updated_at": "TEXT",
            }.items():
                if name not in user_columns:
                    con.execute(f"ALTER TABLE app_users ADD COLUMN {name} {definition}")
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_patient_created
                ON comparison_sessions(patient_id, created_at DESC)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_cobb_patient_path_date
                ON cobb_measurements(patient_id, dicom_path, exam_date DESC)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_patient_created
                ON audit_events(patient_id, created_at DESC)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_labels_patient_path
                ON vertebra_labels(patient_id, dicom_path, created_at)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_image_notes_patient_path
                ON image_notes(patient_id, dicom_path, created_at DESC)
            """)

    def add_exam(
        self,
        *,
        patient_id: str,
        exam_date: str,
        dicom_path: str,
        patient_name: str = "",
        body_part: str = "",
        modality: str = "DX",
        study_description: str = "",
        notes: str = "",
    ) -> int:
        """Insert once; repeated imports of the same DICOM are ignored."""
        patient_id = str(patient_id or "UNKNOWN").strip() or "UNKNOWN"
        exam_date = str(exam_date or "UNKNOWN").strip() or "UNKNOWN"
        dicom_path = str(Path(dicom_path).resolve())

        with self.connection() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO exams
                (patient_id, patient_name, exam_date, body_part, modality,
                 study_description, dicom_path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (patient_id, patient_name, exam_date, body_part, modality,
                 study_description, dicom_path, notes),
            )
            row = con.execute(
                """SELECT id FROM exams
                   WHERE patient_id=? AND exam_date=? AND dicom_path=?""",
                (patient_id, exam_date, dicom_path),
            ).fetchone()
            return int(row[0])

    def add_many(self, exams: Iterable[dict[str, Any]]) -> list[int]:
        """Register a batch in one SQLite transaction (fast folder import)."""
        rows: list[tuple[str, str, str, str, str, str, str, str]] = []
        for exam in exams:
            patient_id = str(exam.get("patient_id") or "UNKNOWN").strip() or "UNKNOWN"
            exam_date = str(exam.get("exam_date") or "UNKNOWN").strip() or "UNKNOWN"
            dicom_path = str(Path(exam.get("dicom_path") or "").resolve())
            rows.append((
                patient_id,
                str(exam.get("patient_name") or ""),
                exam_date,
                str(exam.get("body_part") or ""),
                str(exam.get("modality") or "DX"),
                str(exam.get("study_description") or ""),
                dicom_path,
                str(exam.get("notes") or ""),
            ))

        if not rows:
            return []

        ids: list[int] = []
        with self.connection() as con:
            con.executemany(
                """INSERT OR IGNORE INTO exams
                   (patient_id, patient_name, exam_date, body_part, modality,
                    study_description, dicom_path, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            for patient_id, _name, exam_date, _body_part, _modality, _description, dicom_path, _notes in rows:
                row = con.execute(
                    """SELECT id FROM exams
                       WHERE patient_id=? AND exam_date=? AND dicom_path=?""",
                    (patient_id, exam_date, dicom_path),
                ).fetchone()
                if row is not None:
                    ids.append(int(row[0]))
        return ids

    def list_patient_exams(self, patient_id: str) -> list[dict[str, Any]]:
        with self.connection() as con:
            rows = con.execute(
                """SELECT * FROM exams
                   WHERE patient_id=?
                   ORDER BY exam_date DESC, id DESC""",
                (str(patient_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_exams(self) -> list[dict[str, Any]]:
        """Return all exams only when the caller explicitly enables demo mode."""
        with self.connection() as con:
            rows = con.execute(
                """SELECT * FROM exams
                   ORDER BY patient_name COLLATE NOCASE, exam_date DESC, id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def list_patients(self, query: str = "") -> list[dict[str, Any]]:
        """List locally indexed DICOM patients; this never edits source metadata."""
        like = f"%{str(query).strip()}%"
        with self.connection() as con:
            rows = con.execute(
                """SELECT e.patient_id, COALESCE(p.display_name, MAX(e.patient_name)) AS patient_name,
                          COUNT(*) AS exam_count, MAX(exam_date) AS latest_exam_date
                   FROM exams AS e
                   LEFT JOIN patient_display_names AS p ON p.patient_id = e.patient_id
                   WHERE e.patient_id LIKE ? OR e.patient_name LIKE ? OR p.display_name LIKE ?
                   GROUP BY e.patient_id
                   ORDER BY patient_name COLLATE NOCASE, e.patient_id""",
                (like, like, like),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_follow_up_schedule(self, days_ahead: int = 30, today: date | None = None) -> list[dict[str, Any]]:
        """Return upcoming and overdue local follow-up dates without changing records."""
        horizon = max(0, min(int(days_ahead), 3650))
        reference_day = today or date.today()
        names = {str(row["patient_id"]): row for row in self.list_patients()}
        with self.connection() as con:
            profiles = con.execute(
                """SELECT patient_id, diagnosis, next_follow_up_date
                   FROM patient_profiles
                   WHERE trim(next_follow_up_date) <> ''"""
            ).fetchall()
        rows: list[dict[str, Any]] = []
        for profile in profiles:
            patient_id = str(profile["patient_id"])
            raw_date = str(profile["next_follow_up_date"] or "").strip()
            normalized = raw_date.replace("-", "")
            try:
                follow_up_date = datetime.strptime(normalized, "%Y%m%d").date()
                remaining = (follow_up_date - reference_day).days
            except ValueError:
                rows.append({
                    "patient_id": patient_id,
                    "patient_name": str(names.get(patient_id, {}).get("patient_name", "Hasta")),
                    "next_follow_up_date": raw_date,
                    "days_until": None,
                    "status": "Tarih biçimi geçersiz",
                    "diagnosis": str(profile["diagnosis"] or ""),
                })
                continue
            if remaining > horizon:
                continue
            if remaining < 0:
                status = f"{abs(remaining)} gün gecikmiş"
            elif remaining == 0:
                status = "Bugün"
            else:
                status = f"{remaining} gün sonra"
            rows.append({
                "patient_id": patient_id,
                "patient_name": str(names.get(patient_id, {}).get("patient_name", "Hasta")),
                "next_follow_up_date": follow_up_date.strftime("%Y-%m-%d"),
                "days_until": remaining,
                "status": status,
                "diagnosis": str(profile["diagnosis"] or ""),
            })
        return sorted(rows, key=lambda row: (row["days_until"] is None, row["days_until"] if row["days_until"] is not None else 999999, row["patient_name"]))

    def set_patient_display_name(self, patient_id: str, display_name: str) -> None:
        """Store a local UI label only; original DICOM patient tags are never modified."""
        with self.connection() as con:
            con.execute(
                """INSERT INTO patient_display_names (patient_id, display_name, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(patient_id) DO UPDATE SET display_name=excluded.display_name, updated_at=CURRENT_TIMESTAMP""",
                (str(patient_id), str(display_name).strip()),
            )

    def quality_issues(self, patient_id: str) -> list[dict[str, Any]]:
        """Return non-destructive local-record checks for the selected patient."""
        issues: list[dict[str, Any]] = []
        exams = self.list_patient_exams(patient_id)
        seen_dates: dict[str, int] = {}
        for exam in exams:
            path = str(exam.get("dicom_path", ""))
            if not Path(path).is_file():
                issues.append({"severity": "Uyarı", "kind": "Eksik DICOM", "details": Path(path).name or path})
            date = str(exam.get("exam_date", ""))
            seen_dates[date] = seen_dates.get(date, 0) + 1
        for date, count in seen_dates.items():
            if date and date != "UNKNOWN" and count > 1:
                issues.append({"severity": "Bilgi", "kind": "Aynı tarihli tetkikler", "details": f"{date}: {count} kayıt"})
        for measurement in self.list_cobb_measurements(patient_id):
            angle = float(measurement.get("angle_degrees", 0))
            if not 0.0 <= angle <= 180.0:
                issues.append({"severity": "Uyarı", "kind": "Geçersiz Cobb değeri", "details": f"Kayıt #{measurement['id']}: {angle:.2f}"})
            if not bool(measurement.get("is_locked")):
                issues.append({"severity": "Bilgi", "kind": "Doğrulanmamış Cobb ölçümü", "details": f"Kayıt #{measurement['id']} taslak durumda."})
        try:
            threshold = float(self.get_setting("follow_up/cobb_alert_threshold", "5") or 5)
        except ValueError:
            threshold = 5.0
        try:
            repeatability_threshold = float(self.get_setting("quality/cobb_repeatability_threshold", "3") or 3)
        except ValueError:
            repeatability_threshold = 3.0
        issues.extend(self.cobb_repeatability_issues(patient_id, repeatability_threshold))
        issues.extend(self.follow_up_alerts(patient_id, threshold))
        return issues

    def cobb_repeatability_issues(self, patient_id: str, threshold: float = 3.0) -> list[dict[str, str]]:
        """Flag material disagreement between the last two measurements of one image.

        This is a quality-control check for repeated manual measurements; it
        does not estimate progression and never makes a clinical diagnosis.
        """
        limit = max(0.1, abs(float(threshold)))
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in self.list_cobb_measurements(patient_id):
            groups.setdefault((str(row.get("dicom_path", "")), str(row.get("side", ""))), []).append(row)
        issues: list[dict[str, str]] = []
        for (path, side), rows in groups.items():
            if len(rows) < 2:
                continue
            latest, previous = rows[0], rows[1]
            difference = abs(float(latest["angle_degrees"]) - float(previous["angle_degrees"]))
            if difference >= limit:
                issues.append({
                    "severity": "Uyarı",
                    "kind": "Cobb tekrar ölçüm farkı",
                    "details": (
                        f"{Path(path).name or 'Görüntü'} ({side.upper() or 'taraf yok'}): "
                        f"son iki manuel ölçüm arasında {difference:.2f}° fark var "
                        f"(eşik: {limit:.1f}°; kayıt #{previous['id']} / #{latest['id']})."
                    ),
                })
        return issues

    def get_follow_up_report_bundle(
        self,
        patient_id: str,
        *,
        angle_threshold: float | None = None,
    ) -> dict[str, Any]:
        """Read all follow-up report sections using one SQLite connection.

        This is read-only and intentionally returns plain dictionaries so the
        PDF/CSV generators can run in a worker without touching Qt objects.
        """
        normalized_patient_id = str(patient_id)
        with self.connection() as con:
            profile_row = con.execute(
                "SELECT * FROM patient_profiles WHERE patient_id=?",
                (normalized_patient_id,),
            ).fetchone()
            profile = dict(profile_row) if profile_row else {
                "patient_id": normalized_patient_id,
                "diagnosis": "",
                "referring_physician": "",
                "treatment_plan": "",
                "next_follow_up_date": "",
                "notes": "",
                "updated_by": "",
                "updated_at": "",
            }
            measurements = [
                dict(row)
                for row in con.execute(
                    """SELECT * FROM cobb_measurements WHERE patient_id = ?
                       ORDER BY exam_date DESC, created_at DESC, id DESC""",
                    (normalized_patient_id,),
                ).fetchall()
            ]
            exams = [
                dict(row)
                for row in con.execute(
                    """SELECT
                           e.*,
                           (SELECT c.angle_degrees
                            FROM cobb_measurements AS c
                            WHERE c.patient_id = e.patient_id AND c.dicom_path = e.dicom_path
                            ORDER BY c.created_at DESC, c.id DESC
                            LIMIT 1) AS latest_cobb,
                           (SELECT c.is_locked
                            FROM cobb_measurements AS c
                            WHERE c.patient_id = e.patient_id AND c.dicom_path = e.dicom_path
                            ORDER BY c.created_at DESC, c.id DESC
                            LIMIT 1) AS latest_cobb_locked,
                           (SELECT COUNT(*)
                            FROM comparison_sessions AS s
                            WHERE s.patient_id = e.patient_id
                              AND (s.reference_path = e.dicom_path OR s.comparison_path = e.dicom_path)
                           ) AS overlay_session_count
                       FROM exams AS e
                       WHERE e.patient_id = ?
                       ORDER BY e.exam_date DESC, e.id DESC""",
                    (normalized_patient_id,),
                ).fetchall()
            ]
            sessions = [
                dict(row)
                for row in con.execute(
                    """SELECT * FROM comparison_sessions
                       WHERE patient_id = ?
                       ORDER BY created_at DESC, id DESC""",
                    (normalized_patient_id,),
                ).fetchall()
            ]
            labels = [
                dict(row)
                for row in con.execute(
                    """SELECT * FROM vertebra_labels
                       WHERE patient_id = ? ORDER BY created_at, id""",
                    (normalized_patient_id,),
                ).fetchall()
            ]
            image_notes = [
                dict(row)
                for row in con.execute(
                    """SELECT * FROM image_notes
                       WHERE patient_id = ? ORDER BY created_at DESC, id DESC""",
                    (normalized_patient_id,),
                ).fetchall()
            ]
            setting_row = con.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key=?",
                ("follow_up/cobb_alert_threshold",),
            ).fetchone()
            configured_threshold = setting_row[0] if setting_row else "5"

        try:
            threshold = float(configured_threshold if angle_threshold is None else angle_threshold)
        except (TypeError, ValueError):
            threshold = 5.0
        alerts = _build_follow_up_alerts(measurements, profile, threshold)
        return {
            "profile": profile,
            "measurements": measurements,
            "exams": exams,
            "sessions": sessions,
            "labels": labels,
            "image_notes": image_notes,
            "alerts": alerts,
        }

    def list_patient_follow_up(self, patient_id: str) -> list[dict[str, Any]]:
        """Read-only per-exam overview used by the follow-up timeline window."""
        with self.connection() as con:
            rows = con.execute(
                """SELECT
                       e.*,
                       (SELECT c.angle_degrees
                        FROM cobb_measurements AS c
                        WHERE c.patient_id = e.patient_id AND c.dicom_path = e.dicom_path
                        ORDER BY c.created_at DESC, c.id DESC
                        LIMIT 1) AS latest_cobb,
                       (SELECT c.is_locked
                        FROM cobb_measurements AS c
                        WHERE c.patient_id = e.patient_id AND c.dicom_path = e.dicom_path
                        ORDER BY c.created_at DESC, c.id DESC
                        LIMIT 1) AS latest_cobb_locked,
                       (SELECT COUNT(*)
                        FROM comparison_sessions AS s
                        WHERE s.patient_id = e.patient_id
                          AND (s.reference_path = e.dicom_path OR s.comparison_path = e.dicom_path)
                       ) AS overlay_session_count
                   FROM exams AS e
                   WHERE e.patient_id = ?
                   ORDER BY e.exam_date DESC, e.id DESC""",
                (str(patient_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_comparison_session(
        self,
        *,
        patient_id: str,
        reference_path: str,
        comparison_path: str,
        overlay_offset_x: float,
        overlay_offset_y: float,
        overlay_scale: float,
        overlay_opacity: float,
        notes: str = "",
        overlay_rotation: float = 0.0,
        reference_window_center: float | None = None,
        reference_window_width: float | None = None,
        comparison_window_center: float | None = None,
        comparison_window_width: float | None = None,
        alignment_score: float | None = None,
    ) -> int:
        """Store an Overlay setup without changing the viewer or DICOM files."""
        with self.connection() as con:
            cur = con.execute(
                """INSERT INTO comparison_sessions
                   (patient_id, reference_path, comparison_path, overlay_offset_x,
                    overlay_offset_y, overlay_scale, overlay_opacity, overlay_rotation,
                    reference_window_center, reference_window_width,
                    comparison_window_center, comparison_window_width, alignment_score, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(patient_id or "UNKNOWN"),
                    str(Path(reference_path).resolve()),
                    str(Path(comparison_path).resolve()),
                    float(overlay_offset_x),
                    float(overlay_offset_y),
                    float(overlay_scale),
                    float(overlay_opacity),
                    float(overlay_rotation),
                    reference_window_center,
                    reference_window_width,
                    comparison_window_center,
                    comparison_window_width,
                    alignment_score,
                    str(notes or ""),
                ),
            )
            return int(cur.lastrowid)

    def list_comparison_sessions(self, patient_id: str) -> list[dict[str, Any]]:
        with self.connection() as con:
            rows = con.execute(
                """SELECT * FROM comparison_sessions
                   WHERE patient_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (str(patient_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_comparison_session(self, session_id: int) -> None:
        """Delete only the saved setup; source DICOM files are never touched."""
        with self.connection() as con:
            con.execute("DELETE FROM comparison_sessions WHERE id = ?", (int(session_id),))

    def update_comparison_session_notes(self, session_id: int, notes: str) -> None:
        with self.connection() as con:
            con.execute("UPDATE comparison_sessions SET notes = ? WHERE id = ?", (str(notes or ""), int(session_id)))

    def add_cobb_measurement(
        self,
        *,
        patient_id: str,
        dicom_path: str,
        exam_date: str,
        side: str,
        angle_degrees: float,
        source_sop_instance_uid: str = "",
        points: list[dict[str, float]] | None = None,
        measurement_method: str = "manual_4_point",
        measurement_version: str = "1",
        created_by: str = "",
        provenance_json: str = "",
        upper_vertebra: str = "",
        lower_vertebra: str = "",
        curve_direction: str = "",
    ) -> int:
        point_data = ""
        if points:
            normalized: list[dict[str, float]] = []
            for point in points:
                try:
                    normalized.append({"x": round(float(point["x"]), 3), "y": round(float(point["y"]), 3)})
                except (KeyError, TypeError, ValueError):
                    raise ValueError("Cobb ölçüm noktaları x/y koordinatları içermelidir.") from None
            if len(normalized) != 4:
                raise ValueError("Cobb ölçümü için tam olarak dört nokta gerekir.")
            point_data = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
        normalized_provenance = ""
        if str(provenance_json or "").strip():
            try:
                provenance_payload = json.loads(str(provenance_json))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("Cobb ölçümü provenance_json geçerli JSON olmalıdır.") from exc
            if not isinstance(provenance_payload, dict):
                raise ValueError("Cobb ölçümü provenance_json nesne biçiminde olmalıdır.")
            normalized_provenance = json.dumps(provenance_payload, separators=(",", ":"), ensure_ascii=True)
        with self.connection() as con:
            cur = con.execute(
                """INSERT INTO cobb_measurements
                   (patient_id, dicom_path, exam_date, side, angle_degrees,
                    source_sop_instance_uid, point_data, measurement_method,
                    measurement_version, created_by, provenance_json, upper_vertebra, lower_vertebra, curve_direction)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(patient_id or "UNKNOWN"),
                    str(Path(dicom_path).resolve()),
                    str(exam_date or "UNKNOWN"),
                    str(side),
                    float(angle_degrees),
                    str(source_sop_instance_uid or ""),
                    point_data,
                    str(measurement_method or "manual_4_point"),
                    str(measurement_version or "1"),
                    str(created_by or ""),
                    normalized_provenance,
                    str(upper_vertebra or ""),
                    str(lower_vertebra or ""),
                    str(curve_direction or ""),
                ),
            )
            return int(cur.lastrowid)

    def list_cobb_measurements(self, patient_id: str) -> list[dict[str, Any]]:
        with self.connection() as con:
            rows = con.execute(
                """SELECT * FROM cobb_measurements WHERE patient_id = ?
                   ORDER BY exam_date DESC, created_at DESC, id DESC""",
                (str(patient_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def previous_cobb_for_pair(
        self,
        patient_id: str,
        upper_vertebra: str,
        lower_vertebra: str,
        curve_direction: str = "",
        *,
        before_measurement_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Return the previous Cobb record for the same end-vertebra pair.

        This is a longitudinal comparison helper only. It does not classify
        progression or make a clinical decision.
        """
        upper = str(upper_vertebra or "").strip()
        lower = str(lower_vertebra or "").strip()
        direction = str(curve_direction or "").strip()
        if not upper or not lower:
            return None

        sql = """
            SELECT * FROM cobb_measurements
            WHERE patient_id=?
              AND upper_vertebra=?
              AND lower_vertebra=?
              AND curve_direction=?
        """
        params: list[Any] = [str(patient_id), upper, lower, direction]
        if before_measurement_id is not None:
            sql += " AND id < ?"
            params.append(int(before_measurement_id))
        sql += " ORDER BY exam_date DESC, created_at DESC, id DESC LIMIT 1"

        with self.connection() as con:
            row = con.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def list_all_cobb_measurements(self) -> list[dict[str, Any]]:
        """Return local measurements for quality/training-data review screens."""
        with self.connection() as con:
            rows = con.execute(
                """SELECT * FROM cobb_measurements
                   ORDER BY patient_id, exam_date DESC, created_at DESC, id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_cobb_measurement(self, measurement_id: int) -> None:
        with self.connection() as con:
            row = con.execute("SELECT is_locked FROM cobb_measurements WHERE id=?", (int(measurement_id),)).fetchone()
            if row is None:
                return
            if bool(row["is_locked"]):
                raise PermissionError("Doğrulanıp kilitlenen Cobb ölçümü kaldırılamaz.")
            con.execute("DELETE FROM cobb_measurements WHERE id = ?", (int(measurement_id),))

    def get_cobb_measurement(self, measurement_id: int) -> dict[str, Any] | None:
        with self.connection() as con:
            row = con.execute("SELECT * FROM cobb_measurements WHERE id=?", (int(measurement_id),)).fetchone()
        return dict(row) if row else None

    def verify_and_lock_cobb_measurement(self, measurement_id: int, verified_by: str, note: str = "") -> None:
        """Freeze an approved local measurement; original DICOM is never modified."""
        with self.connection() as con:
            row = con.execute("SELECT id FROM cobb_measurements WHERE id=?", (int(measurement_id),)).fetchone()
            if row is None:
                raise ValueError("Cobb ölçüm kaydı bulunamadı.")
            con.execute(
                """UPDATE cobb_measurements
                   SET is_locked=1, verified_by=?, verified_at=CURRENT_TIMESTAMP, verification_note=?
                   WHERE id=?""",
                (str(verified_by).strip(), str(note or ""), int(measurement_id)),
            )

    def update_cobb_measurement(self, measurement_id: int, angle_degrees: float) -> None:
        with self.connection() as con:
            row = con.execute("SELECT is_locked FROM cobb_measurements WHERE id=?", (int(measurement_id),)).fetchone()
            if row is None:
                raise ValueError("Cobb ölçüm kaydı bulunamadı.")
            if bool(row["is_locked"]):
                raise PermissionError("Doğrulanıp kilitlenen Cobb ölçümü değiştirilemez.")
            con.execute(
                "UPDATE cobb_measurements SET angle_degrees = ? WHERE id = ?",
                (float(angle_degrees), int(measurement_id)),
            )

    def record_audit_event(
        self, patient_id: str, event_type: str, details: str = "", *, actor: str = "", actor_role: str = ""
    ) -> int:
        with self.connection() as con:
            if not actor:
                row = con.execute("SELECT setting_value FROM app_settings WHERE setting_key='active_user_name'").fetchone()
                actor = str(row[0]) if row else ""
            if not actor_role and actor:
                row = con.execute("SELECT role FROM app_users WHERE display_name=?", (str(actor),)).fetchone()
                actor_role = str(row[0]) if row else ""
            cur = con.execute(
                """INSERT INTO audit_events (patient_id, event_type, details, actor, actor_role)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(patient_id or "UNKNOWN"), str(event_type), str(details or ""), str(actor or ""), str(actor_role or "")),
            )
            return int(cur.lastrowid)

    def list_audit_events(self, patient_id: str) -> list[dict[str, Any]]:
        with self.connection() as con:
            rows = con.execute(
                """SELECT * FROM audit_events WHERE patient_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (str(patient_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_exam(self, exam_id: int) -> dict[str, Any] | None:
        with self.connection() as con:
            row = con.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        return dict(row) if row else None

    def delete_exam(self, exam_id: int) -> None:
        with self.connection() as con:
            con.execute("DELETE FROM exams WHERE id=?", (exam_id,))

    def get_patient_profile(self, patient_id: str) -> dict[str, Any]:
        with self.connection() as con:
            row = con.execute("SELECT * FROM patient_profiles WHERE patient_id=?", (str(patient_id),)).fetchone()
        return dict(row) if row else {
            "patient_id": str(patient_id), "diagnosis": "", "referring_physician": "", "treatment_plan": "",
            "next_follow_up_date": "", "notes": "", "updated_by": "", "updated_at": "",
        }

    def save_patient_profile(self, patient_id: str, profile: dict[str, Any], updated_by: str = "") -> None:
        values = (
            str(patient_id), str(profile.get("diagnosis", "")), str(profile.get("referring_physician", "")),
            str(profile.get("treatment_plan", "")), str(profile.get("next_follow_up_date", "")),
            str(profile.get("notes", "")), str(updated_by or ""),
        )
        with self.connection() as con:
            con.execute(
                """INSERT INTO patient_profiles
                   (patient_id, diagnosis, referring_physician, treatment_plan, next_follow_up_date, notes, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(patient_id) DO UPDATE SET
                     diagnosis=excluded.diagnosis, referring_physician=excluded.referring_physician,
                     treatment_plan=excluded.treatment_plan, next_follow_up_date=excluded.next_follow_up_date,
                     notes=excluded.notes, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP""",
                values,
            )

    def add_vertebra_label(
        self, *, patient_id: str, dicom_path: str, vertebra: str, x: float, y: float, note: str = "", created_by: str = ""
    ) -> int:
        with self.connection() as con:
            cur = con.execute(
                """INSERT INTO vertebra_labels(patient_id, dicom_path, vertebra, x, y, note, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(patient_id), str(Path(dicom_path).resolve()), str(vertebra), float(x), float(y), str(note or ""), str(created_by or "")),
            )
            return int(cur.lastrowid)

    def list_vertebra_labels(self, patient_id: str, dicom_path: str = "") -> list[dict[str, Any]]:
        with self.connection() as con:
            if dicom_path:
                rows = con.execute(
                    """SELECT * FROM vertebra_labels WHERE patient_id=? AND dicom_path=?
                       ORDER BY created_at, id""",
                    (str(patient_id), str(Path(dicom_path).resolve())),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM vertebra_labels WHERE patient_id=? ORDER BY created_at, id", (str(patient_id),)
                ).fetchall()
        return [dict(row) for row in rows]

    def delete_vertebra_label(self, label_id: int) -> None:
        with self.connection() as con:
            con.execute("DELETE FROM vertebra_labels WHERE id=?", (int(label_id),))

    def add_image_note(self, *, patient_id: str, dicom_path: str, note: str, created_by: str = "") -> int:
        """Store a local image note; the source DICOM is never modified."""
        text = str(note or "").strip()
        if not text:
            raise ValueError("Görüntü notu boş olamaz.")
        if len(text) > 4000:
            raise ValueError("Görüntü notu en fazla 4000 karakter olabilir.")
        with self.connection() as con:
            cur = con.execute(
                """INSERT INTO image_notes(patient_id, dicom_path, note, created_by)
                   VALUES (?, ?, ?, ?)""",
                (str(patient_id), str(Path(dicom_path).resolve()), text, str(created_by or "")),
            )
            return int(cur.lastrowid)

    def list_image_notes(self, patient_id: str, dicom_path: str = "") -> list[dict[str, Any]]:
        with self.connection() as con:
            if dicom_path:
                rows = con.execute(
                    """SELECT * FROM image_notes WHERE patient_id=? AND dicom_path=?
                       ORDER BY created_at DESC, id DESC""",
                    (str(patient_id), str(Path(dicom_path).resolve())),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM image_notes WHERE patient_id=? ORDER BY created_at DESC, id DESC",
                    (str(patient_id),),
                ).fetchall()
        return [dict(row) for row in rows]

    def update_image_note(self, note_id: int, note: str) -> None:
        """Update only the local note text; source DICOM and note ownership are unchanged."""
        text = str(note or "").strip()
        if not text:
            raise ValueError("Görüntü notu boş olamaz.")
        if len(text) > 4000:
            raise ValueError("Görüntü notu en fazla 4000 karakter olabilir.")
        with self.connection() as con:
            row = con.execute("SELECT id FROM image_notes WHERE id=?", (int(note_id),)).fetchone()
            if row is None:
                raise ValueError("Görüntü notu bulunamadı.")
            con.execute("UPDATE image_notes SET note=? WHERE id=?", (text, int(note_id)))

    def delete_image_note(self, note_id: int) -> None:
        with self.connection() as con:
            con.execute("DELETE FROM image_notes WHERE id=?", (int(note_id),))

    def list_users(self) -> list[dict[str, Any]]:
        with self.connection() as con:
            rows = con.execute(
                """SELECT id, display_name, role, active, created_at, password_updated_at,
                          CASE WHEN password_hash <> '' THEN 1 ELSE 0 END AS password_protected
                   FROM app_users WHERE active=1 ORDER BY role, display_name COLLATE NOCASE"""
            ).fetchall()
        return [dict(row) for row in rows]

    def add_user(self, display_name: str, role: str) -> int:
        if role not in {"Yönetici", "Hekim", "Teknisyen"}:
            raise ValueError("Geçersiz kullanıcı rolü.")
        with self.connection() as con:
            cur = con.execute("INSERT INTO app_users(display_name, role) VALUES (?, ?)", (str(display_name).strip(), role))
            return int(cur.lastrowid)

    @staticmethod
    def _password_digest(password: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, 390000).hex()

    def set_user_password(self, user_id: int, password: str) -> None:
        """Set a local role-switch password using a salted PBKDF2 hash.

        This is a local accountability safeguard, not a replacement for a
        hospital identity provider or central single sign-on service.
        """
        if len(str(password)) < 8:
            raise ValueError("Yerel kullanıcı parolası en az 8 karakter olmalıdır.")
        salt = os.urandom(16)
        with self.connection() as con:
            row = con.execute("SELECT id FROM app_users WHERE id=? AND active=1", (int(user_id),)).fetchone()
            if row is None:
                raise ValueError("Kullanıcı bulunamadı.")
            con.execute(
                """UPDATE app_users SET password_salt=?, password_hash=?, password_updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (salt.hex(), self._password_digest(str(password), salt), int(user_id)),
            )

    def clear_user_password(self, user_id: int) -> None:
        with self.connection() as con:
            con.execute(
                "UPDATE app_users SET password_salt='', password_hash='', password_updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(user_id),),
            )

    def authenticate_user(self, user_id: int, password: str) -> dict[str, Any] | None:
        """Return the safe user record only if its configured local password matches."""
        with self.connection() as con:
            row = con.execute("SELECT * FROM app_users WHERE id=? AND active=1", (int(user_id),)).fetchone()
        if row is None:
            return None
        user = dict(row)
        salt_hex, stored = str(user.get("password_salt", "")), str(user.get("password_hash", ""))
        if not stored:
            return {key: value for key, value in user.items() if key not in {"password_salt", "password_hash"}}
        try:
            digest = self._password_digest(str(password), bytes.fromhex(salt_hex))
        except ValueError:
            return None
        if not hmac.compare_digest(digest, stored):
            return None
        return {key: value for key, value in user.items() if key not in {"password_salt", "password_hash"}}

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connection() as con:
            row = con.execute("SELECT setting_value FROM app_settings WHERE setting_key=?", (str(key),)).fetchone()
        return str(row[0]) if row else str(default)

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as con:
            con.execute(
                """INSERT INTO app_settings(setting_key, setting_value) VALUES (?, ?)
                   ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP""",
                (str(key), str(value)),
            )

    def configure_local_user(self, display_name: str, role: str, *, replace_default: bool = False) -> dict[str, Any]:
        """Create or update a local user selected by the first-use flow."""
        name = str(display_name).strip()
        if not name:
            raise ValueError("Kullanıcı adı boş bırakılamaz.")
        if role not in {"Yönetici", "Hekim", "Teknisyen"}:
            raise ValueError("Geçersiz kullanıcı rolü.")
        with self.connection() as con:
            row = con.execute("SELECT * FROM app_users WHERE display_name=?", (name,)).fetchone()
            if row is not None:
                con.execute("UPDATE app_users SET role=?, active=1 WHERE id=?", (role, int(row["id"])))
                user_id = int(row["id"])
            else:
                default = con.execute(
                    "SELECT * FROM app_users WHERE display_name='Yerel Yönetici' AND active=1"
                ).fetchone()
                active_count = int(con.execute("SELECT COUNT(*) FROM app_users WHERE active=1").fetchone()[0])
                if replace_default and default is not None and active_count == 1:
                    user_id = int(default["id"])
                    con.execute(
                        "UPDATE app_users SET display_name=?, role=? WHERE id=?",
                        (name, role, user_id),
                    )
                else:
                    cur = con.execute(
                        "INSERT INTO app_users(display_name, role) VALUES (?, ?)",
                        (name, role),
                    )
                    user_id = int(cur.lastrowid)
            selected = con.execute("SELECT * FROM app_users WHERE id=?", (user_id,)).fetchone()
        result = dict(selected)
        result.pop("password_salt", None)
        result.pop("password_hash", None)
        return result

    @staticmethod
    def _longitudinal_pair_key(row: dict[str, Any]) -> tuple[str, str, str] | None:
        upper = str(row.get("upper_vertebra", "") or "").strip()
        lower = str(row.get("lower_vertebra", "") or "").strip()
        direction = str(row.get("curve_direction", "") or "").strip()
        if not upper or not lower:
            return None
        return upper, lower, direction

    @staticmethod
    def _one_cobb_per_exam_date(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return one representative measurement per exam date.

        Repeated measurements on the same exam are quality/repeatability data,
        not additional longitudinal time points. Prefer a locked record; when
        none is locked, prefer the newest measurement.
        """
        by_date: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            exam_date = str(row.get("exam_date", "") or "").strip()
            if not exam_date:
                continue
            by_date.setdefault(exam_date, []).append(row)

        selected: list[dict[str, Any]] = []
        for group in by_date.values():
            chosen = max(
                group,
                key=lambda row: (
                    bool(row.get("is_locked")),
                    str(row.get("created_at", "") or ""),
                    int(row.get("id", 0) or 0),
                ),
            )
            selected.append(chosen)

        return sorted(
            selected,
            key=lambda row: (
                str(row.get("exam_date", "") or ""),
                str(row.get("created_at", "") or ""),
                int(row.get("id", 0) or 0),
            ),
        )

    def longitudinal_cobb_series(self, patient_id: str) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
        """Group Cobb history by end-vertebra pair, curve direction and distinct exam date."""
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for row in self.list_cobb_measurements(patient_id):
            key = self._longitudinal_pair_key(row)
            if key is None:
                continue
            groups.setdefault(key, []).append(row)

        return {
            key: self._one_cobb_per_exam_date(rows)
            for key, rows in groups.items()
        }

    def follow_up_alerts(self, patient_id: str, angle_threshold: float = 5.0) -> list[dict[str, str]]:
        """Return follow-up flags only; this function never makes a diagnosis."""
        return _build_follow_up_alerts(
            self.list_cobb_measurements(patient_id),
            self.get_patient_profile(patient_id),
            angle_threshold,
        )



def _build_follow_up_alerts(
    measurements: list[dict[str, Any]],
    profile: dict[str, Any],
    angle_threshold: float = 5.0,
) -> list[dict[str, str]]:
    """Build numeric follow-up flags from already loaded report data."""
    alerts: list[dict[str, str]] = []
    limit = abs(float(angle_threshold))
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in measurements:
        upper = str(row.get("upper_vertebra", "") or "").strip()
        lower = str(row.get("lower_vertebra", "") or "").strip()
        direction = str(row.get("curve_direction", "") or "").strip()
        if upper and lower:
            groups.setdefault((upper, lower, direction), []).append(row)

    for (upper, lower, direction), rows in groups.items():
        by_date: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            exam_date = str(row.get("exam_date", "") or "").strip()
            if exam_date:
                by_date.setdefault(exam_date, []).append(row)
        series: list[dict[str, Any]] = []
        for same_date in by_date.values():
            series.append(
                max(
                    same_date,
                    key=lambda row: (
                        bool(row.get("is_locked")),
                        str(row.get("created_at", "") or ""),
                        int(row.get("id", 0) or 0),
                    ),
                )
            )
        series.sort(
            key=lambda row: (
                str(row.get("exam_date", "") or ""),
                str(row.get("created_at", "") or ""),
                int(row.get("id", 0) or 0),
            )
        )
        if len(series) < 2:
            continue
        previous, latest = series[-2], series[-1]
        previous_angle = float(previous["angle_degrees"])
        latest_angle = float(latest["angle_degrees"])
        delta = latest_angle - previous_angle
        if abs(delta) >= limit:
            alerts.append({
                "severity": "Uyarı",
                "kind": f"Cobb değişimi ({upper}–{lower}{' | ' + direction if direction else ''})",
                "details": (
                    f"{previous.get('exam_date', '—')} → {latest.get('exam_date', '—')}: "
                    f"{previous_angle:.2f}° → {latest_angle:.2f}° "
                    f"(Δ {delta:+.2f}°; eşik: {limit:.1f}°). "
                    "Bu yalnızca sayısal takip uyarısıdır; klinik değerlendirme gerektirir."
                ),
            })

    follow_up = str(profile.get("next_follow_up_date", "") or "").strip()
    if follow_up:
        parsed = None
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(follow_up, fmt).date()
                break
            except ValueError:
                pass
        if parsed is None:
            alerts.append({
                "severity": "Bilgi",
                "kind": "Kontrol tarihi",
                "details": "Kontrol tarihi YYYYMMDD veya YYYY-AA-GG biçiminde olmalı.",
            })
        elif parsed <= date.today():
            alerts.append({
                "severity": "Uyarı",
                "kind": "Kontrol zamanı",
                "details": f"Planlanan takip tarihi geldi/geçti: {follow_up}.",
            })
    return alerts
