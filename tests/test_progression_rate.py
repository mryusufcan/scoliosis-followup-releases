from datetime import datetime

def annualized(first_date, last_date, first_angle, last_angle):
    d1 = datetime.strptime(first_date, "%Y%m%d").date()
    d2 = datetime.strptime(last_date, "%Y%m%d").date()
    days = (d2 - d1).days
    assert days > 0
    return (last_angle - first_angle) / days * 365.25

rate = annualized("20260415", "20261012", 9.27, 51.23)
print(f"Rate: {rate:+.2f}°/yıl")
assert 84.0 < rate < 86.0
print("[OK] Progression-rate math test passed.")
