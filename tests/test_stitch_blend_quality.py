from modular_app.core.stitching_engine import StitchingEngine

engine = StitchingEngine()

good = engine.assess_alignment_quality([(0, 120, 0.60), (2, 110, 0.52)])
assert good["status"] == "good"

warn = engine.assess_alignment_quality([(0, 120, 0.25)])
assert warn["status"] == "warning"

poor = engine.assess_alignment_quality([(0, 120, 0.10)])
assert poor["status"] == "poor"

print("[OK] Stitch blend/quality guard test passed.")
