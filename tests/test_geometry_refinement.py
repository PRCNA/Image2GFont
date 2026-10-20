import copy
import unittest
import numpy as np
from image_pipeline.appearance_metrics import render_ink,compare_ink
from image_pipeline.refine_geometry import refine_geometry,topology


class GeometryRefinementTests(unittest.TestCase):
    def test_offset_curve_improves_with_bounded_motion(self):
        truth=[[(20,30),(60,30),(100,30)]]
        paths=[[(20,30),(60,30.7),(100,30)]];original=copy.deepcopy(paths)
        image=render_ink(truth,3)
        result,info=refine_geometry(image,paths,3)
        self.assertGreater(compare_ink(image,render_ink(result,3))['soft_overlap_iou'],compare_ink(image,render_ink(paths,3))['soft_overlap_iou'])
        self.assertLessEqual(info['max_displacement'],.750001)
        self.assertEqual(paths,original)

    def test_exact_shared_junctions_and_closed_seams_stay_fixed(self):
        paths=[[(20,50),(50,50),(80,50)],[(50,20),(50,50),(50,80)],[(100,100),(130,100),(130,130),(100,100)]]
        image=render_ink(paths,3);result,_=refine_geometry(image,paths,3)
        np.testing.assert_array_equal(result[0][1],paths[0][1]);np.testing.assert_array_equal(result[1][1],paths[1][1])
        self.assertEqual(result[2][0],result[2][-1])
        self.assertEqual(topology(render_ink(result,3)),topology(image))

    def test_perfect_shape_not_degraded_or_reordered(self):
        paths=[[(20,20),(80,20)],[(20,60),(80,60)]]
        image=render_ink(paths,3);result,info=refine_geometry(image,paths,3)
        np.testing.assert_array_equal(result,paths);self.assertEqual(info['accepted'],[])

    def test_blank_and_empty_safe(self):
        paths=[[(20,20),(40,20)]]
        result,_=refine_geometry(np.full((200,200),255),paths,3)
        np.testing.assert_array_equal(result,paths)
        self.assertEqual(refine_geometry(np.full((200,200),255),[],3)[0],[])

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):refine_geometry(np.zeros((10,10)),[],3,max_step=5)
        with self.assertRaises(ValueError):refine_geometry(np.zeros((10,9)),[],3)
