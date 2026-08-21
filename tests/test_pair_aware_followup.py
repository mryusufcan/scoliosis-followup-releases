import tempfile
from pathlib import Path

from modular_app.database.exam_repository import ExamRepository


def add(repo, date, angle, upper, lower, locked=False):
    fake = Path(tempfile.gettempdir()) / f"{date}_{angle}_{upper}_{lower}.dcm"
    mid = repo.add_cobb_measurement(
        patient_id="P1",
        dicom_path=str(fake),
        exam_date=date,
        side="viewer",
        angle_degrees=angle,
        upper_vertebra=upper,
        lower_vertebra=lower,
    )
    if locked:
        repo.verify_and_lock_cobb_measurement(mid, "Test Hekim")
    return mid


with tempfile.TemporaryDirectory() as td:
    repo = ExamRepository(Path(td) / "test.db")

    # T9-L3: two dates, delta -8 => alert expected.
    add(repo, "20260101", 30.0, "T9", "L3")
    add(repo, "20260701", 22.0, "T9", "L3")

    # Same-date repeat should NOT create a third longitudinal point.
    add(repo, "20260701", 40.0, "T9", "L3")

    # C5-T6: only one date => no longitudinal alert.
    add(repo, "20260701", 50.0, "C5", "T6")

    series = repo.longitudinal_cobb_series("P1")

    def matching_rows(upper, lower):
        rows = []
        for key, values in series.items():
            if isinstance(key, tuple) and len(key) >= 2 and key[0] == upper and key[1] == lower:
                rows.extend(values)
        return rows

    t9_l3_rows = matching_rows("T9", "L3")
    c5_t6_rows = matching_rows("C5", "T6")

    assert len(t9_l3_rows) == 2, t9_l3_rows
    assert len(c5_t6_rows) == 1, c5_t6_rows

    alerts = repo.follow_up_alerts("P1", 5.0)
    pair_alerts = [a for a in alerts if "T9–L3" in a["kind"]]
    assert len(pair_alerts) == 1, alerts

    print("[OK] Pair-aware longitudinal follow-up test passed.")
    print(pair_alerts[0]["details"])
