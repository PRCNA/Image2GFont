import unittest
import numpy as np
from vision_core.smoothing import smooth_path


class SmoothingTests(unittest.TestCase):
    def test_staircase_error_reduced_and_endpoints_fixed(self):
        p=[[x,round(x*.4)+10] for x in range(60)]
        q=np.asarray(smooth_path(p))
        self.assertEqual(q[0].tolist(),p[0]);self.assertEqual(q[-1].tolist(),p[-1])
        self.assertLess(np.mean((q[:,1]-.4*q[:,0]-10)**2),np.mean([(y-.4*x-10)**2 for x,y in p]))
    def test_right_angle_preserved(self):
        p=[[x,0] for x in range(21)]+[[20,y] for y in range(1,21)]
        q=smooth_path(p)
        self.assertIn([20.,0.],q)
        self.assertTrue(all(abs(y)<1e-9 or abs(x-20)<1e-9 for x,y in q))
    def test_short_marks_and_disabled_unchanged(self):
        p=[[0,0],[1,1],[2,0]]
        self.assertEqual(smooth_path(p),p)
        self.assertEqual(smooth_path(p*3,max_shift=0),p*3)
    def test_closed_path_remains_closed(self):
        p=[[10+8*np.cos(t),10+8*np.sin(t)] for t in np.linspace(0,2*np.pi,60)]
        p[-1]=p[0]
        q=smooth_path(p);self.assertEqual(q[0],q[-1])
    def test_mask_and_shift_constraint(self):
        p=[[x,10+(x%2)] for x in range(2,60)]
        mask=np.ones((30,70),dtype=bool)
        q=smooth_path(p,mask,max_shift=.3)
        self.assertTrue(all(min(np.linalg.norm(np.asarray(v)-u) for u in p)<=.3+1e-8 for v in q))
    def test_invalid_bound(self):
        with self.assertRaises(ValueError):smooth_path([[0,0]],max_shift=-1)
