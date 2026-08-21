import numpy as np
from modular_app.core.stitching_engine import StitchingEngine

engine = StitchingEngine()

# Two grayscale BGRA strips with a 100px overlap and a modest exposure difference.
h, w, overlap = 500, 300, 100
top = np.zeros((h, w, 4), dtype=np.uint8)
bottom = np.zeros((h, w, 4), dtype=np.uint8)

# Smooth vertical anatomy-like gradient.
g1 = np.linspace(70, 180, h, dtype=np.float32)[:, None]
g2 = np.linspace(82, 192, h, dtype=np.float32)[:, None]
for c in range(3):
    top[..., c] = np.clip(g1, 0, 255).astype(np.uint8)
    bottom[..., c] = np.clip(g2, 0, 255).astype(np.uint8)
top[..., 3] = 255
bottom[..., 3] = 255

out = engine.compose_stitched(
    arrays=[top, bottom],
    part_keys=["servical", "dorsal"],
    paths=["top", "bottom"],
    junction_offsets=[(0.0, float(overlap), 0.8)],
    part_offsets={"servical": [0, 0], "dorsal": [0, 0]},
    gray_flags={"top": True, "bottom": True},
    gray_cache={"top": top[..., 0].astype(np.float32),
                "bottom": bottom[..., 0].astype(np.float32)},
)

assert out is not None
gray = out[..., 0].astype(np.float32)

# The junction must not contain a one-row hard step.
row_mean = gray.mean(axis=1)
max_step = float(np.max(np.abs(np.diff(row_mean))))
print(f"Max row-to-row seam step: {max_step:.2f}")
assert max_step < 8.0, max_step

print("[OK] Complementary feather seam continuity test passed.")
