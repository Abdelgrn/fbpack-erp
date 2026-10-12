import hashlib, json, os, shutil, tempfile, zipfile
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

MAX_FILES = 50000

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def create_full_backup():
    work=Path(tempfile.mkdtemp(prefix='fbpack_backup_'))
    db=work/'database.json'
    with db.open('w',encoding='utf-8') as out:
        call_command('dumpdata', exclude=['sessions.session'], natural_foreign=True, natural_primary=True, indent=2, stdout=out)
    media=Path(settings.MEDIA_ROOT)
    manifest={'format':'FBPACK-FULL-BACKUP','version':1,'created_at':timezone.now().isoformat(),'database_engine':settings.DATABASES['default']['ENGINE'],'files':{'database.json':sha256(db)},'media_files':0}
    archive=work/f"FBPACK_TOTAL_{timezone.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as z:
        z.write(db,'database.json')
        if media.exists():
            for i,path in enumerate(p for p in media.rglob('*') if p.is_file()):
                if i>=MAX_FILES: raise RuntimeError('Nombre de fichiers media excessif.')
                rel=path.relative_to(media).as_posix(); arc=f'media/{rel}'
                z.write(path,arc); manifest['files'][arc]=sha256(path); manifest['media_files']+=1
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return archive,work

def validate_and_extract(uploaded):
    work=Path(tempfile.mkdtemp(prefix='fbpack_restore_')); archive=work/'upload.zip'
    with archive.open('wb') as f:
        for chunk in uploaded.chunks(): f.write(chunk)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if 'manifest.json' not in names or 'database.json' not in names: raise ValueError('Archive FB PACK invalide.')
        for name in names:
            target=(work/'extract'/name).resolve()
            if not str(target).startswith(str((work/'extract').resolve())): raise ValueError('Chemin dangereux dans archive.')
        z.extractall(work/'extract')
    root=work/'extract'; manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format')!='FBPACK-FULL-BACKUP': raise ValueError('Format incompatible.')
    for rel,digest in manifest.get('files',{}).items():
        path=root/rel
        if not path.is_file() or sha256(path)!=digest: raise ValueError(f'Contrôle SHA-256 échoué: {rel}')
    return root,work

def restore_media(root):
    source=root/'media'; target=Path(settings.MEDIA_ROOT)
    if not source.exists(): return
    target.mkdir(parents=True,exist_ok=True)
    for path in source.rglob('*'):
        if path.is_file():
            dest=target/path.relative_to(source); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dest)
