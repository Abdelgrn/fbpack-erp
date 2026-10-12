import hashlib,json,os,shutil,sys,urllib.request
from datetime import datetime
from pathlib import Path
CFG=Path(os.environ.get('PROGRAMDATA',Path.home()))/'FBPACKBackup'/'config.json'
ROOT=Path.home()/'Documents'/'FB PACK - Sauvegardes ERP'
def log(s):
 ROOT.mkdir(parents=True,exist_ok=True); (ROOT/'backup.log').open('a',encoding='utf-8').write(f'[{datetime.now():%F %T}] {s}\n')
def main():
 cfg=json.loads(CFG.read_text(encoding='utf-8')); url=cfg['erp_url'].rstrip('/')+'/administration/backup/download/'
 req=urllib.request.Request(url,headers={'Authorization':'Bearer '+cfg['token'],'User-Agent':'FBPACK-Backup-Agent/1.0'})
 day=ROOT/'Quotidiennes';day.mkdir(parents=True,exist_ok=True);tmp=day/'download.tmp'
 with urllib.request.urlopen(req,timeout=600) as r, tmp.open('wb') as f: shutil.copyfileobj(r,f)
 name=r.headers.get_filename() or f'FBPACK_TOTAL_{datetime.now():%Y%m%d_%H%M%S}.zip'; final=day/name;tmp.replace(final)
 import zipfile
 with zipfile.ZipFile(final) as z:
  m=json.loads(z.read('manifest.json')); assert m['format']=='FBPACK-FULL-BACKUP'
 for p in sorted(day.glob('*.zip'),key=lambda x:x.stat().st_mtime,reverse=True)[30:]: p.unlink()
 log('OK '+str(final))
if __name__=='__main__':
 try: main()
 except Exception as e: log('ERREUR '+repr(e));sys.exit(1)
