import copy
import math
import unittest
import numpy as np
from image_pipeline.junction_candidates import junction_candidates
from image_pipeline.core import candidate_strokes
from image_pipeline.appearance_metrics import render_ink


def star(angles):
    center=[50.,50.]
    return dict(nodes=[],edges=[dict(id=i,start=0,end=i+1,points=[center,[50+30*math.cos(math.radians(a)),50+30*math.sin(math.radians(a))]]) for i,a in enumerate(angles)])


class JunctionTests(unittest.TestCase):
    def test_cross_has_clear_opposite_pairs_and_identical_ink(self):
        graph=star([0,90,180,270]);original=copy.deepcopy(graph)
        paths,report=junction_candidates(graph)
        self.assertEqual(report[0]['status'],'accepted')
        self.assertEqual(sorted(sorted(s['edge_ids']) for s in paths),[[0,2],[1,3]])
        np.testing.assert_array_equal(render_ink([e['points'] for e in graph['edges']],3),render_ink([s['points'] for s in paths],3))
        self.assertEqual(graph,original)

    def test_symmetric_three_way_requires_review(self):
        graph=star([0,120,240]);paths,report=junction_candidates(graph)
        self.assertEqual(report[0]['status'],'review')
        self.assertEqual(paths,candidate_strokes(graph))

    def test_dense_junction_bounded_and_preserved(self):
        graph=star(list(range(0,360,45)));paths,report=junction_candidates(graph)
        self.assertEqual(report[0]['reason'],'degree cap')
        self.assertEqual(sorted(i for s in paths for i in s['edge_ids']),list(range(8)))

    def test_loop_and_isolated_dot_survive(self):
        graph=dict(edges=[dict(id=0,start=0,end=0,points=[[10,10],[20,10],[20,20],[10,10]]),dict(id=1,start=1,end=1,points=[[40,40]])])
        paths,_=junction_candidates(graph)
        self.assertEqual([s['points'] for s in paths],[e['points'] for e in graph['edges']])

    def test_invalid_width(self):
        with self.assertRaises(ValueError):junction_candidates(star([0,180]),pen_width=0)
