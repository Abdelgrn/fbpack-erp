import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

MAX_FILES = 50000
# Limites contre les « bombes zip » (petite archive qui se décompresse en téraoctets).
MAX_UNCOMPRESSED_BYTES = int(getattr(settings, 'BACKUP_MAX_UNCOMPRESSED_BYTES', 5 * 1024 * 1024 * 1024))
MAX_MEMBER_BYTES = int(getattr(settings, 'BACKUP_MAX_MEMBER_BYTES', 2 * 1024 * 1024 * 1024))
ALLOWED_TOP_LEVEL = ('manifest.json', 'database.json')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def create_full_backup():
    work = Path(tempfile.mkdtemp(prefix='fbpack_backup_'))
    try:
        db = work / 'database.json'
        with db.open('w', encoding='utf-8') as out:
            call_command('dumpdata', exclude=['sessions.session'], natural_foreign=True,
                         natural_primary=True, indent=2, stdout=out)
        media = Path(settings.MEDIA_ROOT)
        manifest = {
            'format': 'FBPACK-FULL-BACKUP', 'version': 1,
            'created_at': timezone.now().isoformat(),
            'database_engine': settings.DATABASES['default']['ENGINE'],
            'files': {'database.json': sha256(db)}, 'media_files': 0,
        }
        archive = work / f"FBPACK_TOTAL_{timezone.now():%Y%m%d_%H%M%S}.zip"
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.write(db, 'database.json')
            if media.exists():
                # Les liens symboliques sont ignorés : ils pourraient pointer hors du dossier media.
                files = (p for p in media.rglob('*') if p.is_file() and not p.is_symlink())
                for i, path in enumerate(files):
                    if i >= MAX_FILES:
                        raise RuntimeError('Nombre de fichiers media excessif.')
                    rel = path.relative_to(media).as_posix()
                    arc = f'media/{rel}'
                    z.write(path, arc)
                    manifest['files'][arc] = sha256(path)
                    manifest['media_files'] += 1
            z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        return archive, work
    except Exception:
        # Aucun dossier temporaire (qui contient toute la base) ne doit rester en cas d'échec.
        shutil.rmtree(work, ignore_errors=True)
        raise


def _is_inside(root, candidate):
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check_member_name(info):
    """Refuse les chemins dangereux, les liens symboliques et les fichiers hors périmètre."""
    name = info.filename
    if not name or '\x00' in name or '\\' in name or name.startswith('/') or (len(name) > 1 and name[1] == ':'):
        raise ValueError('Chemin dangereux dans archive.')
    parts = name.split('/')
    if any(part == '..' for part in parts):
        raise ValueError('Chemin dangereux dans archive.')
    # Lien symbolique (bits Unix de external_attr).
    if ((info.external_attr >> 16) & 0o170000) == 0o120000:
        raise ValueError('Lien symbolique interdit dans archive.')
    if name.endswith('/'):
        return
    if name not in ALLOWED_TOP_LEVEL and not name.startswith('media/'):
        raise ValueError(f'Fichier inattendu dans archive : {name}')


def validate_and_extract(uploaded):
    work = Path(tempfile.mkdtemp(prefix='fbpack_restore_'))
    try:
        archive = work / 'upload.zip'
        with archive.open('wb') as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        root = work / 'extract'
        root.mkdir()
        extracted = set()
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            names = {info.filename for info in infos}
            if 'manifest.json' not in names or 'database.json' not in names:
                raise ValueError('Archive FB PACK invalide.')
            if len(infos) > MAX_FILES + 10:
                raise ValueError('Archive : nombre de fichiers excessif.')

            declared_total = 0
            for info in infos:
                _check_member_name(info)
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ValueError('Archive : fichier trop volumineux.')
                declared_total += info.file_size
            if declared_total > MAX_UNCOMPRESSED_BYTES:
                raise ValueError('Archive : taille décompressée excessive.')

            written_total = 0
            for info in infos:
                if info.filename.endswith('/'):
                    continue
                target = root / info.filename
                if not _is_inside(root, target):
                    raise ValueError('Chemin dangereux dans archive.')
                target.parent.mkdir(parents=True, exist_ok=True)
                # Copie par blocs avec compteur réel : un en-tête mensonger ne contourne pas la limite.
                written = 0
                with z.open(info) as src, open(target, 'wb') as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b''):
                        written += len(chunk)
                        written_total += len(chunk)
                        if written > MAX_MEMBER_BYTES or written_total > MAX_UNCOMPRESSED_BYTES:
                            raise ValueError('Archive : taille décompressée excessive.')
                        dst.write(chunk)
                extracted.add(info.filename)

        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('format') != 'FBPACK-FULL-BACKUP':
            raise ValueError('Format incompatible.')
        listed = manifest.get('files', {})
        if not isinstance(listed, dict) or 'database.json' not in listed:
            raise ValueError('Manifeste invalide.')
        # Tout fichier extrait doit être déclaré (et donc contrôlé) dans le manifeste.
        unexpected = extracted - set(listed) - {'manifest.json'}
        if unexpected:
            raise ValueError('Fichier non déclaré dans le manifeste : ' + sorted(unexpected)[0])
        for rel, digest in listed.items():
            path = root / rel
            if not _is_inside(root, path) or not path.is_file() or sha256(path) != digest:
                raise ValueError(f'Contrôle SHA-256 échoué: {rel}')
        return root, work
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise


def restore_media(root):
    source = root / 'media'
    target = Path(settings.MEDIA_ROOT)
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob('*'):
        if path.is_file() and not path.is_symlink():
            dest = target / path.relative_to(source)
            if not _is_inside(target, dest):
                raise ValueError('Chemin média dangereux.')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
