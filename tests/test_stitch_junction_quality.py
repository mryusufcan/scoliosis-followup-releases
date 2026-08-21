from modular_app.core.stitching_engine import StitchingEngine

engine = StitchingEngine()

q = engine.assess_alignment_quality([
    (0.0, 120.0, 0.82),
    (1.0, 110.0, 0.76),
])
assert q["status"] == "good"
assert len(q["junctions"]) == 2
assert q["junctions"][0]["status"] == "good"
assert q["junctions"][1]["status"] == "good"
assert abs(q["average_score"] - 0.79) < 1e-9

q2 = engine.assess_alignment_quality([
    (0.0, 120.0, 0.82),
    (1.0, 110.0, 0.12),
])
assert q2["status"] == "poor"
assert q2["poor_count"] == 1

print("[OK] Per-junction stitch quality test passed.")
