import unittest
import numpy as np
from scipy import ndimage as ndi
from image_pipeline.component_guard import preserve_components


def holes(mask):return ndi.label(ndi.binary_fill_holes(mask)&~mask)[1]


class TopologyGuardTests(unittest.TestCase):
    def test_closed_hole_cannot_be_filled(self):
        seed=np.zeros((9,9),bool);seed[2:7,2:7]=True;seed[3:6,3:6]=False
        result,info=preserve_components(seed,np.ones_like(seed),True)
        self.assertEqual(holes(result),1)
        self.assertGreater(info['hole_pixels_rejected'],0)

    def test_open_counter_cannot_be_closed(self):
        seed=np.zeros((9,9),bool);seed[2:7,2:7]=True;seed[3:6,3:6]=False;seed[2,4]=False
        candidate=seed.copy();candidate[2,4]=True
        result,_=preserve_components(seed,candidate,True)
        self.assertFalse(result[2,4]);self.assertEqual(holes(result),0)
        self.assertTrue(preserve_components(seed,candidate)[0][2,4])

    def test_border_growth_does_not_make_fake_hole(self):
        seed=np.zeros((7,7),bool);seed[0:3,0:3]=True
        result,_=preserve_components(seed,np.ones_like(seed),True)
        self.assertEqual(holes(result),0)
        self.assertTrue(result.all())

    def test_two_diagonally_adjacent_holes_remain_separate(self):
        seed=np.ones((7,7),bool);seed[2,2]=False;seed[3,3]=False
        result,_=preserve_components(seed,np.ones_like(seed),True)
        self.assertEqual(holes(result),2)

    def test_random_masks_preserve_both_topologies(self):
        rng=np.random.default_rng(4837)
        for _ in range(100):
            seed=rng.random((9,11))<.4;candidate=rng.random(seed.shape)<.8
            original=seed.copy()
            result,_=preserve_components(seed,candidate,True)
            self.assertEqual(holes(seed),holes(result))
            self.assertEqual(ndi.label(seed,np.ones((3,3)))[1],ndi.label(result,np.ones((3,3)))[1])
            self.assertTrue(result[seed].all())
            np.testing.assert_array_equal(seed,original)

    def test_invalid_flag(self):
        with self.assertRaises(ValueError):
            preserve_components(np.ones((3,3),bool),np.ones((3,3),bool),1)
