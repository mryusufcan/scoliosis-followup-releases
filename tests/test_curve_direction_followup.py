from tempfile import TemporaryDirectory
from pathlib import Path
from modular_app.database.exam_repository import ExamRepository

with TemporaryDirectory() as td:
    repo = ExamRepository(Path(td) / "test.db")
    for date, angle, direction in [
        ("20260101", 30, "Sağ konveks"),
        ("20260701", 24, "Sağ konveks"),
        ("20260101", 18, "Sol konveks"),
        ("20260701", 20, "Sol konveks"),
    ]:
        repo.add_cobb_measurement(
            patient_id="P1",
            dicom_path=str(Path(td) / f"{date}_{angle}_{direction}.dcm"),
            exam_date=date,
            side="viewer",
            angle_degrees=angle,
            upper_vertebra="T9",
            lower_vertebra="L3",
            curve_direction=direction,
        )

    series = repo.longitudinal_cobb_series("P1")
    assert len(series[("T9", "L3", "Sağ konveks")]) == 2
    assert len(series[("T9", "L3", "Sol konveks")]) == 2

    alerts = repo.follow_up_alerts("P1", 5.0)
    assert any("Sağ konveks" in a["kind"] for a in alerts)
    assert not any("Sol konveks" in a["kind"] for a in alerts)

    print("[OK] Curve-direction-aware follow-up test passed.")
