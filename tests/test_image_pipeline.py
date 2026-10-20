import unittest
import numpy as np
from scipy import ndimage as ndi
from image_pipeline.core import skeletonize, graph_from_skeleton, candidate_strokes, prune_spurs, simplify


class SkeletonGraphTests(unittest.TestCase):
    def test_solid_bar_becomes_connected_centerline(self):
        mask = np.zeros((40, 70), bool)
        mask[15:25, 5:65] = True
        thin = skeletonize(mask)
        self.assertEqual(ndi.label(thin, np.ones((3, 3)))[1], 1)
        self.assertLess(thin.sum(), 70)
        self.assertTrue(np.array_equal(skeletonize(thin), thin))

    def test_cross_keeps_four_arms_and_pairs_two_paths(self):
        mask = np.zeros((61, 61), bool)
        mask[30, 5:56] = True
        mask[5:56, 30] = True
        graph = graph_from_skeleton(mask)
        self.assertEqual(len(graph['edges']), 4)
        paths = candidate_strokes(graph)
        self.assertEqual(len(paths), 2)
        self.assertEqual(sorted(i for s in paths for i in s['edge_ids']), list(range(4)))

    def test_loop_is_preserved(self):
        mask = np.zeros((30, 30), bool)
        mask[5, 5:25] = mask[24, 5:25] = True
        mask[5:25, 5] = mask[5:25, 24] = True
        graph = graph_from_skeleton(mask)
        self.assertEqual(len(graph['edges']), 1)
        path = graph['edges'][0]['points']
        self.assertEqual(path[0], path[-1])
        self.assertGreater(len(simplify(path)), 4)

    def test_two_adjacent_pixels_are_not_collapsed(self):
        mask = np.zeros((8, 8), bool)
        mask[3, 3:5] = True
        graph = graph_from_skeleton(mask)
        self.assertEqual(len(graph['edges']), 1)
        self.assertEqual(len(graph['edges'][0]['points']), 2)

    def test_pruning_does_not_delete_separate_dot(self):
        mask = np.zeros((50, 50), bool)
        mask[30, 5:46] = True
        mask[27:30, 25] = True
        mask[4, 4] = True
        cleaned, removed = prune_spurs(mask, 5)
        self.assertGreater(removed, 0)
        self.assertTrue(cleaned[4, 4])
        self.assertTrue(cleaned[30, 5:46].all())

    def test_disconnected_strokes_stay_disconnected(self):
        mask = np.zeros((40, 40), bool)
        mask[10, 4:30] = True
        mask[20, 4:30] = True
        self.assertEqual(len(candidate_strokes(graph_from_skeleton(mask))), 2)


if __name__ == '__main__':
    unittest.main()
