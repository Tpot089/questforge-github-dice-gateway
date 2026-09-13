#!/usr/bin/env python3
"""Claim before RNG; persist result before comment. Ambiguous execution never rerolls."""
import base64,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path

def encoded(x):return (json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def api(path,method='GET',payload=None):
    args=['gh','api','--method',method,path]
    if payload is not None:args+=['--input','-']
    p=subprocess.run(args,input=json.dumps(payload) if payload is not None else None,capture_output=True,text=True)
    if p.returncode:
        # Only confirmed 404 is absence. Network/auth errors must stop.
        if method=='GET' and 'HTTP 404' in p.stderr:return None
        raise RuntimeError('GitHub durability operation failed: '+p.stderr)
    return json.loads(p.stdout)
def get(repo,path):
    r=api(f'repos/{repo}/contents/{path}')
    if r is None:return None
    return json.loads(base64.b64decode(r['content']))
def create(repo,path,value):
    # No existing SHA supplied: GitHub rejects duplicate creation, providing a claim CAS.
    return api(f'repos/{repo}/contents/{path}','PUT',{'message':'QuestForge durable '+path,'content':base64.b64encode(encoded(value)).decode()})
def execute(event,output,get_record=get,create_record=create,run=subprocess.run):
    issue=event['issue'];repo=event['repository']['full_name'];number=int(issue['number'])
    if issue.get('author_association') not in ['OWNER','MEMBER','COLLABORATOR']:raise RuntimeError('roll requests restricted to repository collaborators')
    request=json.loads(issue['body']);request_hash=hashlib.sha256(encoded(request)).hexdigest();prefix=f'questforge-receipts/issue-{number}'
    result=get_record(repo,prefix+'-result.json')
    if result:
        if result['request_sha256']!=request_hash:raise RuntimeError('issue body changed since execution')
        Path(output).write_text(result['receipt_markdown']);return result
    claim=get_record(repo,prefix+'-claim.json')
    if claim:raise RuntimeError('execution already claimed, result unavailable: RECOVERY REQUIRED; never reroll')
    claim={'schema':1,'issue':number,'request':request,'request_sha256':request_hash,'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'gateway_commit':os.environ.get('GITHUB_SHA')}
    create_record(repo,prefix+'-claim.json',claim)
    # A crash from this point through result persistence is an explicit unresolved claim.
    with tempfile.TemporaryDirectory() as td:
        ep=Path(td)/'event.json';ep.write_bytes(encoded(event));out=Path(td)/'receipt.md'
        p=run([sys.executable,str(Path(__file__).with_name('github_issue_roll.py')),str(ep),str(out)],capture_output=True,text=True)
        if p.returncode:raise RuntimeError('execution failed after durable claim; inspect run, do not retry RNG')
        result=dict(claim,receipt_markdown=out.read_text(),status='executed')
        create_record(repo,prefix+'-result.json',result)
        verified=get_record(repo,prefix+'-result.json')
        if verified!=result:raise RuntimeError('result readback failed; no success claim')
        Path(output).write_text(result['receipt_markdown'])
    return result
if __name__=='__main__':execute(json.loads(Path(sys.argv[1]).read_text()),sys.argv[2])
