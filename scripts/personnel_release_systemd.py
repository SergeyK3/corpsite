"""Plan a last-priority release drop-in; preserve and verify existing files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

CONFIG_ROOT=Path('/etc/systemd/system')
UNITS=('corpsite-backend.service','corpsite-frontend.service')


def fingerprint(path):
    info=path.stat()
    return {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode':info.st_mode & 0o777,'uid':info.st_uid,'gid':info.st_gid}


def exec_argv(value):
    matches=re.findall(r'\{ path=([^;]+?) ; argv\[\]=([^;]+?) ;',value)
    if len(matches)!=1:raise RuntimeError('Expected exactly one ExecStart')
    executable,arguments=matches[0]
    argv=shlex.split(arguments)
    if not argv or argv[0]!=executable:raise RuntimeError('ExecStart path/argv mismatch')
    return argv


def probe(unit):
    value=subprocess.check_output(['systemctl','show',unit,'--no-pager',
        '-p','DropInPaths','-p','WorkingDirectory','-p','ExecStart'],text=True)
    properties=dict(line.split('=',1) for line in value.splitlines() if '=' in line)
    return {'paths':properties['DropInPaths'].split(),
            'directory':properties['WorkingDirectory'],'argv':exec_argv(properties['ExecStart'])}


def last_name(paths,sha):
    names=[Path(path).name for path in paths]
    prefix=max(names,key=lambda value:value.encode()) if names else 'zz-release'
    result=prefix+'.personnel-'+sha+'.conf'
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',result) or len(result.encode())>255:
        raise RuntimeError('Cannot safely choose a last-priority drop-in filename')
    if any(result.encode()<=name.encode() for name in names):raise RuntimeError('Drop-in priority conflict')
    return result


def desired(sha,unit):
    if not re.fullmatch('[0-9a-f]{40}',sha):raise RuntimeError('Invalid release SHA')
    root='/opt/projects/corpsite/releases/'+sha
    if unit==UNITS[0]:
        directory=root
        argv=[root+'/.venv/bin/python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000']
        environment=''
    elif unit==UNITS[1]:
        directory=root+'/corpsite-ui'
        argv=['/usr/bin/node',directory+'/node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3000']
        environment='Environment=NEXT_DEPLOYMENT_ID='+sha+'\n'
    else:raise RuntimeError('Unsupported service')
    body='[Service]\nWorkingDirectory='+directory+'\n'+environment+'ExecStart=\nExecStart='+' '.join(argv)+'\n'
    return {'directory':directory,'argv':argv,'body':body}


def prepare(sha,*,inspect=probe,config_root=CONFIG_ROOT):
    result={'format':'personnel-systemd-switch-v1','sha':sha,'units':{}}
    for unit in UNITS:
        wanted=desired(sha,unit);original=inspect(unit)
        target=config_root/(unit+'.d')/last_name(original['paths'],sha)
        if target.exists():raise RuntimeError('Release drop-in already exists')
        result['units'][unit]={'original':original,'files':{p:fingerprint(Path(p)) for p in original['paths']},
            'target':str(target),'desired':wanted}
    return result


def validate(plan,*,config_root=CONFIG_ROOT):
    if plan.get('format')!='personnel-systemd-switch-v1' or set(plan['units'])!=set(UNITS):
        raise RuntimeError('Invalid systemd switch plan')
    for unit,entry in plan['units'].items():
        expected=config_root/(unit+'.d')/last_name(entry['original']['paths'],plan['sha'])
        if entry['target']!=str(expected) or entry['desired']!=desired(plan['sha'],unit):
            raise RuntimeError('Switch plan target/content mismatch')
        if set(entry['files'])!=set(entry['original']['paths']):raise RuntimeError('Incomplete original drop-in evidence')
        for path,evidence in entry['files'].items():
            if fingerprint(Path(path))!=evidence:raise RuntimeError('Existing drop-in changed: '+path)


def install(plan,*,config_root=CONFIG_ROOT):
    validate(plan,config_root=config_root)
    for entry in plan['units'].values():
        if Path(entry['target']).exists():raise RuntimeError('Refusing to overwrite a drop-in')
    for entry in plan['units'].values():
        path=Path(entry['target']);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8',newline='\n') as stream:stream.write(entry['desired']['body'])
        path.chmod(0o644)


def remove(plan,*,config_root=CONFIG_ROOT):
    validate(plan,config_root=config_root)
    for entry in plan['units'].values():
        path=Path(entry['target'])
        if path.exists() and path.read_bytes()!=entry['desired']['body'].encode():
            raise RuntimeError('Refusing to remove a modified release drop-in')
    for entry in plan['units'].values():Path(entry['target']).unlink(missing_ok=True)


def verify(plan,*,original=False,inspect=probe,config_root=CONFIG_ROOT):
    validate(plan,config_root=config_root)
    for unit,entry in plan['units'].items():
        current=inspect(unit)
        expected=entry['original'] if original else entry['desired']
        paths=entry['original']['paths']+([] if original else [entry['target']])
        if current['paths']!=paths:raise RuntimeError('Effective DropInPaths/priority mismatch: '+unit)
        if current['directory']!=expected['directory'] or current['argv']!=expected['argv']:
            raise RuntimeError('Effective WorkingDirectory/ExecStart mismatch: '+unit)
        if not original and Path(entry['target']).read_bytes()!=expected['body'].encode():
            raise RuntimeError('Release drop-in contents changed')
    return {'verified':True,'original':original,'units':list(UNITS),'sha':plan['sha']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','install','verify','remove','verify-original'))
    parser.add_argument('--sha');parser.add_argument('--output',type=Path);parser.add_argument('--plan',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':
        plan=prepare(args.sha)
        with args.output.open('x',encoding='utf-8') as stream:json.dump(plan,stream,indent=2)
        print(json.dumps({'prepared':True,'targets':{u:e['target'] for u,e in plan['units'].items()}}));return
    plan=json.loads(args.plan.read_text(encoding='utf-8'))
    if args.action=='install':install(plan)
    elif args.action=='remove':remove(plan)
    else:print(json.dumps(verify(plan,original=args.action=='verify-original')))


if __name__=='__main__':main()
