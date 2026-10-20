import unittest
import numpy as np
from validate_public_handwriting import component_relations


class ExternalMetricTests(unittest.TestCase):
    def test_merge_is_not_removal(self):
        a=np.zeros((10,10),bool);a[4,1:3]=True;a[4,6:8]=True
        b=a.copy();b[4,3:6]=True
        r=component_relations(a,b)
        self.assertEqual(r['merged_reference_groups'],[[1,2]])
        self.assertEqual(r['removed_reference_components'],[])

    def test_removal_and_split(self):
        a=np.zeros((10,10),bool);a[4,1:8]=True;a[8,8]=True
        b=a.copy();b[4,4]=False;b[8,8]=False
        r=component_relations(a,b)
        self.assertEqual(r['merged_reference_groups'],[])
        self.assertEqual(r['removed_reference_components'],[2])
        self.assertEqual(r['split_reference_components'],[1])

    def test_unchanged(self):
        a=np.eye(5,dtype=bool)
        self.assertTrue(all(not x for x in component_relations(a,a).values()))
