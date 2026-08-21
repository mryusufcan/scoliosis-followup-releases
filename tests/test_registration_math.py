import math
import unittest

import cv2
import numpy as np


MIN_INLIER_RATIO = 0.45


def make_test_image(width=900, height=1400):
    img = np.zeros((height, width), dtype=np.uint8)

    cv2.rectangle(img, (160, 90), (740, 1310), 90, 3)
    cv2.line(img, (450, 120), (450, 1280), 170, 8)

    for y in range(180, 1230, 70):
        cv2.ellipse(img, (450, y), (90, 24), 0, 0, 360, 220, 3)

    for x in (280, 620):
        for y in range(220, 1200, 120):
            cv2.circle(img, (x, y), 18, 200, 2)

    cv2.line(img, (260, 300), (640, 460), 180, 5)
    cv2.line(img, (250, 1040), (650, 900), 180, 5)
    cv2.putText(img, "REG", (320, 760), cv2.FONT_HERSHEY_SIMPLEX, 2.0, 255, 4)

    return img


def estimate_similarity(reference, moving):
    orb = cv2.ORB_create(
        nfeatures=5000,
        scaleFactor=1.2,
        nlevels=8,
        fastThreshold=7,
    )

    kp_ref, des_ref = orb.detectAndCompute(reference, None)
    kp_mov, des_mov = orb.detectAndCompute(moving, None)

    if des_ref is None or des_mov is None:
        raise AssertionError("Descriptor üretilemedi.")

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    pairs = matcher.knnMatch(des_mov, des_ref, k=2)

    good = []
    for pair in pairs:
        if len(pair) != 2:
            continue
        m, n = pair
        if m.distance < 0.78 * n.distance:
            good.append(m)

    if len(good) < 10:
        raise AssertionError(f"Yeterli eşleşme yok: {len(good)}")

    src = np.float32([kp_mov[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_ref[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    matrix, inliers = cv2.estimateAffinePartial2D(
        src,
        dst,
        method=cv2.RANSAC,
        ransacReprojThreshold=5.0,
        maxIters=4000,
        confidence=0.995,
        refineIters=25,
    )

    if matrix is None or inliers is None:
        raise AssertionError("Affine dönüşüm hesaplanamadı.")

    a = float(matrix[0, 0])
    b = float(matrix[1, 0])

    return {
        "dx": float(matrix[0, 2]),
        "dy": float(matrix[1, 2]),
        "scale": math.hypot(a, b),
        "rotation": math.degrees(math.atan2(b, a)),
        "inlier_ratio": float(inliers.ravel().astype(bool).mean()),
        "good_matches": len(good),
        "inliers": int(inliers.ravel().astype(bool).sum()),
    }


class RegistrationMathTests(unittest.TestCase):
    def setUp(self):
        self.ref = make_test_image()
        self.h, self.w = self.ref.shape[:2]

    def test_translation(self):
        expected_dx = 120
        expected_dy = -180

        matrix = np.float32([
            [1.0, 0.0, expected_dx],
            [0.0, 1.0, expected_dy],
        ])
        moving = cv2.warpAffine(
            self.ref, matrix, (self.w, self.h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        result = estimate_similarity(self.ref, moving)
        print("\ntranslation:", result)

        self.assertAlmostEqual(result["dx"], -expected_dx, delta=4.0)
        self.assertAlmostEqual(result["dy"], -expected_dy, delta=4.0)
        self.assertAlmostEqual(result["scale"], 1.0, delta=0.02)
        self.assertAlmostEqual(result["rotation"], 0.0, delta=0.5)
        self.assertGreater(result["inlier_ratio"], MIN_INLIER_RATIO)

    def test_zoom(self):
        applied_scale = 0.92
        matrix = cv2.getRotationMatrix2D(
            (self.w / 2.0, self.h / 2.0),
            0.0,
            applied_scale,
        )
        moving = cv2.warpAffine(
            self.ref, matrix, (self.w, self.h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        result = estimate_similarity(self.ref, moving)
        print("\nzoom:", result)

        self.assertAlmostEqual(result["scale"], 1.0 / applied_scale, delta=0.03)
        self.assertAlmostEqual(result["rotation"], 0.0, delta=0.5)
        self.assertGreater(result["inlier_ratio"], MIN_INLIER_RATIO)

    def test_rotation(self):
        applied_rotation = 4.0
        matrix = cv2.getRotationMatrix2D(
            (self.w / 2.0, self.h / 2.0),
            applied_rotation,
            1.0,
        )
        moving = cv2.warpAffine(
            self.ref, matrix, (self.w, self.h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        result = estimate_similarity(self.ref, moving)
        print("\nrotation:", result)

        self.assertAlmostEqual(abs(result["rotation"]), applied_rotation, delta=0.6)
        self.assertAlmostEqual(result["scale"], 1.0, delta=0.02)
        self.assertGreater(result["inlier_ratio"], MIN_INLIER_RATIO)


if __name__ == "__main__":
    unittest.main()
