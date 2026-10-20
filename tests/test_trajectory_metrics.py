import unittest
import numpy as np
from image_pipeline.trajectory_metrics import match_strokes,resample


class TrajectoryMetricTests(unittest.TestCase):
    def test_exact_and_unequal_sampling(self):
        a=[[(0,0),(30,0)],[(0,20),(30,20)]]
        b=[[(0,0),(10,0),(20,0),(30,0)],a[1]]
        self.assertTrue(match_strokes(a,b)['full_ordered_directed_match'])

    def test_reversal_and_order_are_distinguished(self):
        a=[[(0,0),(30,0)],[(0,20),(30,20)]]
        for b in [a[::-1],[a[0][::-1],a[1]]]:
            r=match_strokes(a,b)
            self.assertTrue(r['full_unordered_match'])
            self.assertFalse(r['full_ordered_directed_match'])

    def test_split_is_not_two_correct_strokes(self):
        r=match_strokes([[(0,0),(40,0)]],[[(0,0),(20,0)],[(20,0),(40,0)]])
        self.assertEqual(r['matched'],0)

    def test_merge_is_not_correct(self):
        r=match_strokes([[(0,0),(20,0)],[(20,0),(40,0)]],[[(0,0),(40,0)]])
        self.assertEqual(r['matched'],0)

    def test_same_count_wrong_geometry(self):
        r=match_strokes([[(0,0),(30,0)]],[[(0,20),(30,20)]])
        self.assertTrue(r['count_equal']);self.assertFalse(r['full_unordered_match'])

    def test_backtracking_is_not_hidden_by_nearest_distance(self):
        a=[[(0,0),(40,0)]];b=[[(0,0),(35,0),(5,0),(40,0)]]
        r=match_strokes(a,b)
        self.assertFalse(r['full_unordered_match'])
        self.assertLess(r['assignments'][0]['p95_distance'],1)

    def test_empty_and_duplicate_points(self):
        self.assertFalse(match_strokes([],[])['full_unordered_match'])
        np.testing.assert_array_equal(resample([(2,3),(2,3)]),[[2,3]])
        self.assertEqual(match_strokes([[(0,0)]],[])['matched'],0)

    def test_duplicate_prediction_cannot_match_twice(self):
        a=[[(0,0),(30,0)]]
        r=match_strokes(a,a+a)
        self.assertEqual(r['matched'],1);self.assertEqual(r['stroke_precision'],.5)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):resample([(float('nan'),0)])
        with self.assertRaises(ValueError):match_strokes([],[],geometry_tolerance=0)
