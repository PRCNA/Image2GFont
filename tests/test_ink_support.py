import unittest
import numpy as np
from image_pipeline.ink_support import supported_mask,local_widths


class InkSupportTests(unittest.TestCase):
    def test_bright_bridge_removed_dark_pixels_preserved(self):
        gray=np.full((12,20),255.);gray[4:8,2:7]=0;gray[4:8,12:17]=0
        mask=gray<128;mask[5,7:12]=True;original=mask.copy()
        result,info=supported_mask(gray,mask)
        self.assertEqual(info['removed_bright_pixels'],5)
        np.testing.assert_array_equal(result,gray<128)
        np.testing.assert_array_equal(mask,original)

    def test_light_connection_retained_below_guard_threshold(self):
        gray=np.array([[0,170,0]],float)
        result,_=supported_mask(gray,np.ones_like(gray,dtype=bool))
        self.assertTrue(result.all())

    def test_width_recovers_straight_band(self):
        gray=np.full((40,60),255.);gray[17:23,5:55]=0
        graph=dict(nodes=[],edges=[dict(id=0,points=[[20,20],[25,20],[30,20]])])
        rows=local_widths(gray,graph)
        for r in rows:self.assertAlmostEqual(r['width'],6,delta=.02)

    def test_junction_width_not_invented(self):
        graph=dict(nodes=[dict(degree=4,point=[10,10])],edges=[dict(id=0,points=[[10,10],[11,10]])])
        self.assertTrue(all(r['width'] is None for r in local_widths(np.zeros((30,30)),graph)))

    def test_invalid_and_empty_graph(self):
        with self.assertRaises(ValueError):supported_mask(np.zeros((2,2)),np.zeros((2,2)))
        self.assertEqual(local_widths(np.full((20,20),255),dict(nodes=[],edges=[])),[])
