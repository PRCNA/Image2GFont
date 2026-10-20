import unittest
import numpy as np
from image_pipeline.appearance_metrics import compare_ink,geometry,travel,render_ink

rasterize=render_ink


class AppearanceMetricTests(unittest.TestCase):
    def test_integer_point_is_centered_on_integer_pixel(self):
        im=render_ink([[(20,20)]],3)
        tile=im[17:24,17:24]
        np.testing.assert_array_equal(tile,tile[::-1,:])
        np.testing.assert_array_equal(tile,tile[:,::-1])

    def test_oblique_reversal_is_exact(self):
        paths=[[(20.2,31.7),(70.8,79.1),(101.3,25.5)]]
        np.testing.assert_array_equal(render_ink(paths,3),render_ink([paths[0][::-1]],3))

    def test_order_direction_and_segmentation_do_not_change_shape(self):
        a=[[(20,20),(80,20)],[(20,50),(80,50)]]
        b=[a[1][::-1],[(80,20),(50,20)],[(50,20),(20,20)]]
        self.assertEqual(compare_ink(rasterize(a,3),rasterize(b,3))['overlap_iou'],1)
        self.assertEqual(geometry(a,b)['reference_to_predicted_p95'],0)
        self.assertEqual(travel(a)['pen_lift_transitions'],1)
        self.assertEqual(travel(b)['pen_lift_transitions'],2)

    def test_missing_and_extra_are_distinct(self):
        a=np.full((8,8),255);a[2,1:6]=0
        b=a.copy();b[2,1]=255;b[5,1:4]=0
        r=compare_ink(a,b)
        self.assertEqual(r['missing_pixels'],1);self.assertEqual(r['extra_pixels'],3)

    def test_no_ink_on_pen_up_move(self):
        a=[[(20,20),(40,20)],[(20,60),(40,60)]]
        im=np.asarray(rasterize(a,3))
        self.assertEqual(im[40,30],255)
        self.assertGreater(travel(a)['pen_up_length'],0)

    def test_duplicate_retrace_detected_even_with_identical_raster(self):
        a=[[(20,20),(80,20)]];b=a+[a[0][::-1]]
        self.assertEqual(compare_ink(rasterize(a,3),rasterize(b,3))['overlap_iou'],1)
        self.assertAlmostEqual(travel(b)['retraced_grid_fraction'],.5)

    def test_crossing_not_duplicate_edge(self):
        a=[[(0,20),(40,20)],[(20,0),(20,40)]]
        self.assertEqual(travel(a)['retraced_grid_length'],0)

    def test_shift_detected_without_auto_alignment(self):
        a=[[(20,20),(80,20)]];b=[[(20,25),(80,25)]]
        self.assertAlmostEqual(geometry(a,b)['reference_to_predicted_p95'],5)
        self.assertLess(compare_ink(rasterize(a,3),rasterize(b,3))['overlap_iou'],.1)

    def test_empty_and_invalid_inputs(self):
        blank=np.full((8,8),255)
        self.assertIsNone(compare_ink(blank,blank)['overlap_iou'])
        self.assertIsNone(geometry([],[])['reference_to_predicted_p95'])
        self.assertEqual(travel([])['pen_up_length'],0)
        with self.assertRaises(ValueError):compare_ink(blank,np.zeros((3,3)))
