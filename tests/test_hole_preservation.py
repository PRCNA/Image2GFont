import unittest
import numpy as np
from image_pipeline.core import preprocess


class HolePreservationTests(unittest.TestCase):
    def test_large_character_counter_preserved_and_tiny_hole_filled(self):
        gray = np.full((90, 90), 230, dtype=np.uint8)
        gray[15:75, 15:75] = 30
        gray[25:65, 25:65] = 230
        gray[19, 19] = 230
        args = dict(blur=0,threshold=20,closing=1,min_area=1,background_sigma=80,silhouette_sigma=0)
        corrected = preprocess(gray, max_hole_area=3, **args)
        self.assertFalse(corrected[45,45])
        self.assertTrue(corrected[19,19])
        legacy = preprocess(gray, **args)
        self.assertTrue(legacy[45,45])

    def test_zero_hole_limit_preserves_tiny_hole(self):
        gray = np.full((50,50),230,dtype=np.uint8)
        gray[15:35,15:35] = 30
        gray[25,25] = 230
        result = preprocess(gray,blur=0,threshold=20,closing=1,min_area=1,
                            background_sigma=80,silhouette_sigma=0,max_hole_area=0)
        self.assertFalse(result[25,25])
