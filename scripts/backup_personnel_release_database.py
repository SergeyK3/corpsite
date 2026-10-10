"""Full pg_dump backup without exposing a database URL or password in argv/logs."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.db.engine import engine

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if engine.url.host not in ('127.0.0.1','localhost','::1') or engine.url.database!='corpsite':raise RuntimeError('Run on the database host only')
 pg_dump=shutil.which('pg_dump')
 if not pg_dump:raise RuntimeError('pg_dump is required before server changes')
 if a.output.exists():raise RuntimeError('Refusing to overwrite database backup')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 env=dict(os.environ,PGPASSWORD=engine.url.password or '')
 command=[pg_dump,'--format=custom','--host',engine.url.host,'--port',str(engine.url.port or 5432),'--username',engine.url.username,'--dbname',engine.url.database,'--file',str(a.output)]
 subprocess.run(command,env=env,check=True)
 if not a.output.stat().st_size:raise RuntimeError('Empty database backup')
 hasher=hashlib.sha256()
 with a.output.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):hasher.update(chunk)
 digest=hasher.hexdigest()
 a.output.with_suffix(a.output.suffix+'.sha256').write_text(digest+'  '+a.output.name+'\n',encoding='ascii')
 print(json.dumps({'backup':str(a.output),'bytes':a.output.stat().st_size,'sha256':digest}))

if __name__=='__main__':main()
