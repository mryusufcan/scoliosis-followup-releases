import numpy as np
from modular_app.core.stitching_engine import StitchingEngine

engine = StitchingEngine()

h, w, overlap = 600, 400, 120

top = np.zeros((h, w, 4), dtype=np.uint8)
bottom = np.zeros((h, w, 4), dtype=np.uint8)

yy, xx = np.indices((h, w))
base = 80 + 0.12 * yy + 15 * np.sin(xx / 17.0) + 10 * np.sin(yy / 23.0)
base = np.clip(base, 0, 255)

for c in range(3):
    top[..., c] = base.astype(np.uint8)
    bottom[..., c] = base.astype(np.uint8)

top[..., 3] = 255
bottom[..., 3] = 255

score, edge, seam = engine.evaluate_junction_quality(
    top, bottom, 0.0, float(overlap), 1.0
)

print("Final:", score, "edge:", edge, "seam:", seam)

# Even with raw phase score 1.0, v2 should remain conservative.
assert score < 1.0
assert score > 0.65

# Extreme shift must be penalized.
bad_score, _, _ = engine.evaluate_junction_quality(
    top, bottom, 120.0, float(overlap), 1.0
)
assert bad_score < score

print("[OK] Stitch Quality Score v2 test passed.")
