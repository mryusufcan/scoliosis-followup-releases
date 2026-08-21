from modular_app.core.stitching_engine import StitchingEngine

engine = StitchingEngine()

good = engine.assess_alignment_quality([
    {"dx": 0, "dy": 120, "score": 0.73, "raw_score": 0.58},
    {"dx": 0, "dy": 110, "score": 0.91, "raw_score": 1.00},
])
assert good["status"] == "good"
assert round(good["average_score"], 2) == 0.82

poor = engine.assess_alignment_quality([
    {"dx": 0, "dy": 120, "score": 0.73},
    {"dx": 0, "dy": 110, "score": 0.12},
])
assert poor["status"] == "poor"

print("[OK] Final verification quality-state test passed.")
