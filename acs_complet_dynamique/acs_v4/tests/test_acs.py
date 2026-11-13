import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acs_v4 import *
class TestACS(unittest.TestCase):
 def test_score(self): self.assertEqual(score_acs({'C':10,'I':10,'A':6,'T':3},WEIGHTS),7.8)
 def test_weight_invalid(self):
  with self.assertRaises(ValueError):score_acs(dict.fromkeys('CIAT',5),dict.fromkeys('CIAT',.3))
 def test_identity_stable(self):
  a={'nom':'serveur-a','source':'lab','source_id':'vm-01'}
  self.assertEqual(identity(a)[0],identity({**a,'nom':'renomme'})[0])
 def test_dedup(self):
  a={'nom':'a','source':'lab','source_id':'id1'}
  self.assertEqual(len(consolidate([a,{**a,'nom':'a2'}])),1)
 def test_topology(self):
  a=consolidate([{'nom':'a'},{'nom':'b'},{'nom':'c'}]);e={(a[0]['id'],a[1]['id'])}
  t=topology(a,e);self.assertEqual(t[a[0]['id']],5.5);self.assertEqual(t[a[2]['id']],1)
 def test_missing_frequency(self):
  rows=process([{'nom':'a','type':'pki'},{'nom':'b','type':'web'}]);self.assertTrue(all(r['freq_mu']=='' for r in rows))
 def test_missing_profile(self):
  r=process([{'nom':'a','type':'inconnu'}])[0];self.assertEqual(r['ACS'],5)
 def test_out_of_range(self):
  with self.assertRaises(ValueError):process([{'nom':'a','C':12}])
 def test_dynamic_addition(self):
  a=[{'nom':'a'},{'nom':'b'}]; initial=consolidate(a)
  e={(initial[0]['id'],initial[1]['id'])};old=topology(initial,e)
  expanded=consolidate(a+[{'nom':'c'}]);new=topology(expanded,e)
  self.assertNotEqual(old[initial[0]['id']],new[initial[0]['id']])
if __name__=='__main__':unittest.main()
