"""Build the reviewed stage-three ZIP from git, never from runtime or a DB."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from uuid import uuid4
import zipfile


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--revision',default='HEAD')
    parser.add_argument('--source-tree',type=Path,help='Reviewed source tree before the initial local commit')
    parser.add_argument('--rehearse',action='store_true')
    args=parser.parse_args();root=args.repo.resolve()
    def git(*command):
        return subprocess.check_output(['git',*command],cwd=root)
    def gitfile(revision,path):
        r=subprocess.run(['git','show',revision+':'+path],cwd=root,capture_output=True)
        return r.stdout if r.returncode==0 else b''
    def release(path):
        if args.source_tree:
            target=args.source_tree.resolve()/path
            if target.is_file():return target.read_bytes().replace(b'\r\n',b'\n')
        return gitfile(args.revision,path).replace(b'\r\n',b'\n')
    scope=json.loads(release('scripts/personnel_template_stage3_files.json'))
    assert all(not p.startswith(('runtime/','docs-work/','.local-backups/')) for p in scope)
    entries={};patch_info=[]
    protected=['app/services/personnel_order_template_initial_data.py','app/services/personnel_order_template_catalog_data.py','corpsite-ui/app/directory/personnel/_lib/personnelOrderCanonicalTitles.ts']
    def legacy(content,path):
        content=content.replace(b'\r\n',b'\n')
        if path.endswith('.py'):content=content.split(b'\nfrom app.services.personnel_order_recall_contract')[0]
        else:content=b'\n'.join(line for line in content.splitlines() if not line.lstrip().startswith(b'"LEAVE.ANNUAL.RECALL":'))
        return content.rstrip()
    for base,name in [('430d248^','stages1-3.patch'),('430d248','stages2-3.patch'),('8cd8c4ec','stage3.patch')]:
        paths={p for p in git('diff','--name-only',base,'8cd8c4ec').decode().splitlines() if not p.endswith('.cjs')}|set(scope)
        patch=[]
        for path in sorted(paths):
            before=gitfile(base,path)
            after=release(path) if path in scope else gitfile('8cd8c4ec',path)
            for line in difflib.unified_diff(before.decode('utf-8').splitlines(True),after.decode('utf-8').splitlines(True),fromfile='a/'+path if before else '/dev/null',tofile='b/'+path):
                patch.append(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
        payload=''.join(patch).encode('utf-8');entries[name]=payload
        patch_info.append({'patch':name,'base':base,'paths':sorted(paths)})
        if args.rehearse:
            destination=root/'runtime/stage3-final'/('package-check-'+uuid4().hex[:8]);destination.mkdir(parents=True)
            with tarfile.open(fileobj=io.BytesIO(git('archive',base))) as archive:
                for member in archive:
                    if not member.isfile():continue
                    target=destination/member.name
                    assert target.resolve().is_relative_to(destination.resolve())
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.extractfile(member).read())
            before_titles={}
            for p in protected:
                target=destination/p
                sentinel=b'// SERVER TITLE SENTINEL\n' if p.endswith('.ts') else b'# SERVER TITLE SENTINEL\n'
                target.write_bytes(sentinel+target.read_bytes())
                before_titles[p]=legacy(target.read_bytes(),p)
            patch_path=destination/'selected.patch';patch_path.write_bytes(payload)
            prefix=str(destination.relative_to(root)).replace('\\','/')
            for command in [['apply','--check'],['apply']]:
                result=subprocess.run(['git',*command,'--directory='+prefix,str(patch_path)],cwd=root,capture_output=True)
                if result.returncode:
                    raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))
            assert all(legacy((destination/p).read_bytes(),p)==before_titles[p] for p in protected)
    for path in scope:
        content=release(path)
        assert content,path
        entries['source/'+path]=content
    entries['DEPLOY.md']=release('docs/deploy/personnel-template-variants.md')
    entries['check_release.py']=release('scripts/personnel_template_variants_release_check.py')
    entries['backup_database.py']=gitfile('8cd8c4ec','scripts/personnel_language_backup_database.py')
    entries['templates/annual-leave-recall.json']=release('reference-data/personnel-templates/annual-leave-recall.json')
    manifest={'revision':'hrrecall001','parents':['orgkk001','hrlang001','hrtpl001'],
              'patches':patch_info,'code_sha256':hashlib.sha256(b''.join(path.encode()+b'\0'+entries['source/'+path] for path in sorted(scope))).hexdigest(),
              'ui_access':{'path':'/admin/templates','capability':'has_sysadmin_api','system_admin_role_fallback':2,'api_rules_unchanged':True},
              'template_import':'Separate, optional independent DRAFT; never automatic publication',
              'excluded':['test users','test roles','personal grants','test publications','test orders','HR events','database dumps','backups','runtime reports','job catalog changes']}
    entries['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    entries['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+path+'\n' for path,data in sorted(entries.items())).encode('ascii')
    name='corpsite-personnel-template-variants-20261006';output=root/'runtime'/(name+'.zip')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name+'/'+path,date_time=(2026,10,7,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n',encoding='ascii',newline='\n')
    print(json.dumps({'zip':str(output),'sha256':digest,'entries':len(entries),'patches_rehearsed':args.rehearse}))


if __name__=='__main__':main()
