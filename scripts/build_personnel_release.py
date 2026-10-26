"""Package immutable Git code and a validated Linux Next build; no deployment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',required=True);p.add_argument('--sha',required=True)
    p.add_argument('--built-checkout',type=Path,required=True)
    p.add_argument('--validation',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    git=lambda *args:subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
    sha=git('rev-parse',a.sha);base=git('rev-parse',a.base)
    if git('rev-parse','master')!=sha:raise RuntimeError('Package must pin current master')
    subprocess.run(['git','merge-base','--is-ancestor',base,sha],cwd=repo,check=True)
    ui=a.built_checkout/'corpsite-ui'
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.built_checkout,text=True).strip()
    if actual!=sha:raise RuntimeError('Build checkout is not the pinned release SHA')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=a.built_checkout,text=True).strip():
        raise RuntimeError('Build checkout has modified tracked files')
    config=json.loads((ui/'.next/required-server-files.json').read_text(encoding='utf-8'))
    if config['config'].get('deploymentId')!=sha:raise RuntimeError('Linux build deploymentId mismatch')
    build_env=json.loads((a.built_checkout/'release-build-environment.json').read_text())
    expected={'NEXT_DEPLOYMENT_ID':sha,'NEXT_PUBLIC_APP_ENV':'prod','NEXT_PUBLIC_API_BASE_URL':'/api','NEXT_PUBLIC_DEV_X_USER_ID':''}
    if build_env!=expected:raise RuntimeError('Production build environment mismatch')
    validation=json.loads(a.validation.read_text(encoding='utf-8'))
    if not validation.get('rehearsal',{}).get('transfer_restore_verified'):raise RuntimeError('No successful isolated restore evidence')
    output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
    payload=output/'payload';payload.mkdir(exist_ok=False)
    bundle=payload/'release-code.bundle'
    subprocess.run(['git','bundle','create',str(bundle),base+'..master'],cwd=repo,check=True)
    subprocess.run(['git','bundle','verify',str(bundle)],cwd=repo,check=True,capture_output=True)
    frontend=payload/'frontend-next-linux.tar.gz'
    # Next creates Linux symlinks for external packages. Windows tarfile cannot
    # read those links from a Docker bind mount; GNU tar preserves them intact.
    subprocess.run(['docker','run','--rm','--pull=never','--network','none',
        '--mount','type=bind,source='+str(a.built_checkout.resolve())+',target=/work,readonly',
        '--mount','type=bind,source='+str(payload)+',target=/output',
        'node:22.14.0-bookworm-slim','tar','-czf','/output/'+frontend.name,
        '--exclude=.next/cache','-C','/work/corpsite-ui','.next'],check=True)
    changed=git('diff','--name-only',base,sha).splitlines()
    commits=git('log','--reverse','--format=%H %s',base+'..'+sha).splitlines()
    (payload/'changed-files.txt').write_text('\n'.join(changed)+'\n',encoding='utf-8')
    (payload/'commits.txt').write_text('\n'.join(commits)+'\n',encoding='utf-8')
    runbook=subprocess.check_output(['git','show',sha+':docs/deploy/personnel-release-runbook-20261026.txt'],cwd=repo).decode('utf-8')
    (payload/'RUNBOOK.txt').write_text(runbook.replace('personnel-release-RELEASE_SHA.tar.gz','personnel-release-'+sha[:12]+'.tar.gz'),encoding='utf-8')
    (payload/'validation-summary.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest={'base_production_sha':base,'source_sha':sha,'canonical_head':'poprint001','canonical_head_count':1,
        'migration_path':['podup001','posdir001','medspec001','poprint001'],
        'frontend_build_id':(ui/'.next/BUILD_ID').read_text().strip(),'frontend_deployment_id':sha,
        'linux_build_image':'node:22.14.0-bookworm-slim','lock_sha256':digest(ui/'package-lock.json'),
        'build_environment':build_env,
        'scope':'code/schema plus explicitly approved dictionary transfer; no production actions executed',
        'excluded':['production dumps','schema-only dump','env/credentials','node_modules','private test connection'],
        'changed_file_count':len(changed),'commits':commits,
        'files':{f.name:{'bytes':f.stat().st_size,'sha256':digest(f)} for f in payload.iterdir()}}
    (payload/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (payload/'SHA256SUMS').write_text(''.join(digest(f)+'  '+f.name+'\n' for f in sorted(payload.iterdir()) if f.name!='SHA256SUMS'),encoding='ascii')
    package=output/('personnel-release-'+sha[:12]+'.tar.gz')
    with tarfile.open(package,'w:gz') as archive:
        for f in sorted(payload.iterdir()):archive.add(f,arcname=f.name)
    package.with_suffix(package.suffix+'.sha256').write_text(digest(package)+'  '+package.name+'\n',encoding='ascii')
    print(json.dumps({'package':str(package),'bytes':package.stat().st_size,'sha256':digest(package),'source_sha':sha,'changed_files':len(changed)}))


if __name__=='__main__':main()
