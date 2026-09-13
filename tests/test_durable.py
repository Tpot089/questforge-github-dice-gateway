import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
s=importlib.util.spec_from_file_location('durable',Path(__file__).parents[1]/'questforge-runtime/scripts/durable_issue_roll.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):self.records={};self.calls=0;self.event={'issue':{'number':1,'body':'{"notation":"d20"}','author_association':'OWNER'},'repository':{'full_name':'fixture/repo'}}
 def get(self,r,p):return self.records.get(p)
 def put(self,r,p,v):
  if p in self.records:raise RuntimeError('CAS conflict')
  self.records[p]=v
 def fake_run(self,args,**kw):self.calls+=1;Path(args[-1]).write_text('synthetic TEST ONLY receipt');return SimpleNamespace(returncode=0)
 def execute(self):
  with tempfile.TemporaryDirectory() as t:return m.execute(self.event,Path(t)/'out',self.get,self.put,self.fake_run)
 def test_rerun_reuses_exact_result(self):a=self.execute();b=self.execute();self.assertEqual(a,b);self.assertEqual(self.calls,1)
 def test_claim_without_result_never_rerolls(self):self.records['questforge-receipts/issue-1-claim.json']={};self.records['questforge-receipts/issue-1-claim.json']={'claimed':True};self.assertRaises(RuntimeError,self.execute);self.assertEqual(self.calls,0)
 def test_edited_request_blocks(self):self.execute();self.event['issue']['body']='{"notation":"d6"}';self.assertRaises(RuntimeError,self.execute);self.assertEqual(self.calls,1)
 def test_outsider_rejected(self):self.event['issue']['author_association']='NONE';self.assertRaises(RuntimeError,self.execute);self.assertEqual(self.calls,0)
 def test_failure_after_claim(self):
  self.fake_run=lambda *a,**kw:SimpleNamespace(returncode=1);self.assertRaises(RuntimeError,self.execute);self.assertRaises(RuntimeError,self.execute)
if __name__=='__main__':unittest.main()
