import unittest
import numpy as np
from scipy import ndimage as ndi
from image_pipeline.component_guard import preserve_components


class ComponentGuardTests(unittest.TestCase):
    def test_bridge_does_not_merge_or_delete_seeds(self):
        seeds=np.zeros((15,20),bool);seeds[4:11,2:6]=True;seeds[4:11,12:16]=True
        proposed=seeds.copy();proposed[6:9,6:12]=True
        a,b=seeds.copy(),proposed.copy()
        result,info=preserve_components(seeds,proposed)
        self.assertEqual(ndi.label(result,np.ones((3,3)))[1],2)
        self.assertTrue(np.all(result[seeds]))
        self.assertGreater(info['conflict_pixels_rejected'],0)
        np.testing.assert_array_equal(a,seeds);np.testing.assert_array_equal(b,proposed)
        np.testing.assert_array_equal(result,preserve_components(seeds,proposed)[0])

    def test_diagonal_contact_is_blocked(self):
        seeds=np.zeros((7,7),bool);seeds[1,1]=True;seeds[4,4]=True
        result,_=preserve_components(seeds,np.ones_like(seeds))
        self.assertEqual(ndi.label(result,np.ones((3,3)))[1],2)

    def test_dot_restored_and_unseeded_region_not_invented(self):
        seeds=np.zeros((10,10),bool);seeds[1,1]=True
        proposed=np.zeros_like(seeds);proposed[7:9,7:9]=True
        result,info=preserve_components(seeds,proposed)
        np.testing.assert_array_equal(result,seeds)
        self.assertEqual(info['seed_pixels_restored'],1)
        self.assertEqual(info['unvisited_candidate_pixels'],4)

    def test_empty_seeds_explicitly_return_empty(self):
        result,info=preserve_components(np.zeros((4,4),bool),np.ones((4,4),bool))
        self.assertFalse(result.any());self.assertTrue(info['no_seeds'])

    def test_seed_fragmentation_is_not_repaired(self):
        # Negative control: two seeds might actually belong to ONE broken stroke.
        seeds=np.zeros((5,9),bool);seeds[2,1:4]=True;seeds[2,5:8]=True
        proposed=seeds.copy();proposed[2,4]=True
        result,_=preserve_components(seeds,proposed)
        self.assertFalse(result[2,4])
        self.assertEqual(ndi.label(result,np.ones((3,3)))[1],2)

    def test_invalid_masks(self):
        for a,b in [(np.zeros((3,3)),np.zeros((3,3),bool)),
                    (np.zeros((3,3),bool),np.zeros((2,2),bool)),
                    (np.zeros((0,0),bool),np.zeros((0,0),bool))]:
            with self.assertRaises(ValueError):preserve_components(a,b)
