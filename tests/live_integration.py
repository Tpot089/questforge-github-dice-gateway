"""Real GitHub transport, authentic QuestForge self-test, no campaign canon."""
import importlib.util,json,os,subprocess,tempfile
from pathlib import Path
s=importlib.util.spec_from_file_location('durable',Path(__file__).parents[1]/'questforge-runtime/scripts/durable_issue_roll.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
repo=os.environ['GITHUB_REPOSITORY'];issue=d.api(f'repos/{repo}/issues/3')
assert issue['title'].startswith('[QF-ROLL]') and 'NONCANONICAL' in issue['title']
assert json.loads(issue['body'])['self_test'] is True
assert issue['author_association'] in ['OWNER','MEMBER','COLLABORATOR']
event={'repository':{'full_name':repo},'issue':issue};executions=[]
def observed_run(args,**kwargs):
 claim=d.get(repo,'NONCANONICAL-INTEGRATION-TEST/issue-3-claim.json');assert claim and claim['request']['self_test'] is True
 executions.append('claim verified before authentic execution')
 return subprocess.run(args,**kwargs)
with tempfile.TemporaryDirectory() as t:
 out=Path(t)/'receipt.md';first=d.execute(event,out,run=observed_run);assert '[SELF-TEST NON-CANON]' in first['receipt_markdown']
 def forbid(*args,**kwargs):raise AssertionError('RETRY ATTEMPTED SECOND ROLL')
 second=d.execute(event,out,run=forbid);assert first==second
 # Prove unresolved claim handling using the same REAL persisted claim, withholding only result lookup.
 def hide_result(repo,path):return None if path.endswith('-result.json') else d.get(repo,path)
 try:d.execute(event,out,get_record=hide_result,run=forbid)
 except RuntimeError as e:assert 'RECOVERY REQUIRED' in str(e)
 else:raise AssertionError('unresolved claim did not block')
 comment=d.api(f'repos/{repo}/issues/3/comments','POST',{'body':first['receipt_markdown']+'\nNONCANONICAL INTEGRATION-TEST: retry returned the same receipt without RNG.'})
 report={'classification':'NONCANONICAL INTEGRATION-TEST','request_accepted':True,'claim_before_rng':True,'durable_result_verified':True,'retry_same_receipt':True,'unresolved_claim_blocks':True,'executions_this_run':len(executions),'run_id':os.environ['GITHUB_RUN_ID'],'comment_url':comment['html_url'],'receipt':first}
 Path('integration-result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
