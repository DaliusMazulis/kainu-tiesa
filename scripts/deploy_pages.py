"""Deploy the uploaded Pages artifact through GitHub's documented REST API.
Uses only the ephemeral GitHub Actions token and OIDC identity of this job.
Artifact lookup, permissions and Pages deployment remain scoped to this repository.
"""
import json
import os
import sys
import time
from urllib.request import Request, urlopen


def request_json(url, token, method='GET', payload=None):
    body=json.dumps(payload).encode() if payload is not None else None
    request=Request(url, data=body, method=method, headers={
        'Authorization':'Bearer '+token,
        'Accept':'application/vnd.github+json',
        'Content-Type':'application/json',
        'X-GitHub-Api-Version':'2022-11-28',
    })
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def deploy(artifact_id, repo, sha, token, oidc_token, api='https://api.github.com', transport=request_json, pause=time.sleep, clock=time.monotonic):
    if not isinstance(artifact_id,int) or artifact_id<=0: raise ValueError('Invalid artifact ID')
    if api!='https://api.github.com' or repo!='DaliusMazulis/kainu-tiesa': raise ValueError('Unexpected deployment destination')
    endpoint=f'{api}/repos/{repo}/pages/deployments'
    # Submit once. Status polling must never create duplicate deployments.
    created=transport(endpoint, token, 'POST', {
        'artifact_id':artifact_id,
        'pages_build_version':sha,
        'oidc_token':oidc_token,
    })
    deployment_id=created.get('id') or created.get('status_url','').rsplit('/',1)[-1]
    page_url=created.get('page_url')
    if not deployment_id or not page_url: raise RuntimeError('Pages API did not return a deployment and URL')
    deadline=clock()+300
    failures={'deployment_failed','deployment_perms_error','deployment_content_failed','deployment_lost','deployment_cancelled','failure','cancelled'}
    while clock()<deadline:
        status=transport(endpoint+'/'+str(deployment_id),token).get('status')
        if status=='succeed': return page_url
        if status in failures: raise RuntimeError('Pages deployment failed: '+status)
        pause(5)
    raise RuntimeError('Pages deployment did not finish within five minutes')


def main():
    env=os.environ
    # Obtain the job's existing OIDC identity without writing or logging credentials.
    oidc=request_json(env['ACTIONS_ID_TOKEN_REQUEST_URL'],env['ACTIONS_ID_TOKEN_REQUEST_TOKEN'])['value']
    page_url=deploy(int(env['PRICE_PAGES_ARTIFACT_ID']),env['GITHUB_REPOSITORY'],env['GITHUB_SHA'],env['PRICE_GITHUB_TOKEN'],oidc,api=env['GITHUB_API_URL'])
    with open(env['GITHUB_OUTPUT'],'a',encoding='utf-8') as output:
        output.write('page_url='+page_url+'\n')
    print('GitHub Pages deployment succeeded.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Do not serialize requests, token values or API response bodies into logs.
        print('Pages deployment failed ('+type(error).__name__+').',file=sys.stderr)
        raise SystemExit(1)
