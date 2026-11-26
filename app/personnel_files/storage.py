"""Private immutable originals and raster previews. Never expose this directory."""
from __future__ import annotations
import hashlib
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from uuid import UUID
import warnings

from PIL import Image
from fastapi import HTTPException

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 20
MAX_PIXELS = 20_000_000


def root() -> Path:
    from app.config import PROJECT_ROOT, env
    configured = env('PERSONNEL_FILE_STORAGE_ROOT')
    if configured:
        path = Path(configured)
        return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
    from app.personnel_intake.infrastructure.photo_storage import intake_photo_storage_root
    return (intake_photo_storage_root() / 'reviewed-files').resolve()


def path(key: str, name: str) -> Path:
    # Both values are server-generated; validate again on reads from the ledger.
    UUID(key)
    if name != 'original' and not (name.startswith('page-') and name.endswith('.png') and name[5:-4].isdigit()):
        raise ValueError('Invalid file component')
    base = root()
    result = (base / key / name).resolve()
    if not result.is_relative_to(base):
        raise ValueError('Storage path escapes root')
    return result


def scan(filename: Path) -> None:
    from app.config import env
    # An operator supplies a scanner command, never the uploaded filename or shell syntax.
    command = shlex.split(env('PERSONNEL_FILE_SCAN_COMMAND', 'clamscan --no-summary'))
    if not command or not shutil.which(command[0]):
        raise HTTPException(503, 'Проверка безопасности файлов не настроена. Обратитесь к администратору.')
    try:
        result = subprocess.run([*command, str(filename)], capture_output=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(503, 'Проверка безопасности временно недоступна.') from exc
    if result.returncode == 1:
        raise HTTPException(422, 'Файл не прошёл проверку безопасности.')
    if result.returncode != 0:
        raise HTTPException(503, 'Проверка безопасности временно недоступна.')


def render(content: bytes, mime: str, kind: str) -> list[bytes]:
    if not content or len(content) > MAX_BYTES:
        raise ValueError('Файл пуст или превышает 10 МиБ.')
    if kind == 'photo':
        from app.personnel_intake.domain.photo_validation import validate_intake_photo_bytes
        from app.personnel_intake.domain.errors import PersonnelIntakeValidationError
        if mime != 'image/jpeg':
            raise ValueError('Для фото лица требуется JPEG.')
        try:
            validate_intake_photo_bytes(content, content_type=mime)
        except PersonnelIntakeValidationError as exc:
            messages = {
                'Photo file is empty.': 'Выберите непустой файл JPEG.',
                'Photo exceeds 500 KB limit.': 'Фото превышает допустимый размер 500 КБ.',
                'Only JPEG photos are accepted.': 'Для фото требуется файл JPEG.',
                'SVG images are not allowed.': 'Файл SVG нельзя использовать как фото.',
                'Unsupported photo content.': 'Содержимое файла не подходит для фото.',
                'Photo must be JPEG.': 'Содержимое файла должно быть JPEG.',
                'Photo could not be decoded as JPEG.': 'Не удалось прочитать файл как JPEG.',
            }
            message = messages.get(str(exc), 'Фото не прошло проверку формата.')
            if str(exc).startswith('Photo must be 600x800 pixels.'):
                message = 'Фото должно иметь размер 600 × 800 пикселей.'
            raise ValueError(message) from exc
    if mime in {'image/jpeg', 'image/png'}:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format != {'image/jpeg': 'JPEG', 'image/png': 'PNG'}[mime]:
                    raise ValueError('Содержимое не соответствует формату файла.')
                if image.width * image.height > MAX_PIXELS or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Изображение слишком большое или содержит несколько кадров.')
                image.load()
                image.thumbnail((1400, 1800))
                out = io.BytesIO()
                image.convert('RGB').save(out, format='PNG')
                return [out.getvalue()]
    if mime != 'application/pdf' or not content.startswith(b'%PDF-'):
        raise ValueError('Разрешены JPEG, PNG и PDF.')
    import pymupdf
    with pymupdf.open(stream=content, filetype='pdf') as doc:
        if doc.is_encrypted or doc.needs_pass or doc.is_repaired or not 1 <= len(doc) <= MAX_PAGES:
            raise ValueError('PDF повреждён, защищён паролем или превышает 20 страниц.')
        if doc.xref_length() > 20_000:
            raise ValueError('PDF содержит слишком много объектов.')
        if doc.embfile_count():
            raise ValueError('PDF с вложенными файлами не принимается.')
        # Inspect parsed objects, not raw substring searches (compressed/escaped PDF names).
        forbidden = {'JS', 'JavaScript', 'AA', 'OpenAction', 'Launch', 'RichMedia', 'XFA', 'EmbeddedFiles', 'AcroForm'}
        for xref in range(1, doc.xref_length()):
            if forbidden.intersection(doc.xref_get_keys(xref)):
                raise ValueError('PDF содержит активные элементы или формы.')
            if doc.xref_get_key(xref, 'S')[1] in {'/JavaScript', '/Launch', '/GoToR', '/SubmitForm', '/ImportData'}:
                raise ValueError('PDF содержит запрещённые действия.')
        pages = []
        for page in doc:
            if page.rect.is_empty or page.rect.is_infinite:
                raise ValueError('Некорректная страница PDF.')
            scale = min(1400 / page.rect.width, 1800 / page.rect.height, 2)
            pages.append(page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png'))
        return pages


def prepare(key: str, content: bytes, mime: str, kind: str) -> tuple[str, int]:
    destination = path(key, 'original')
    try:
        # On Windows, mode=0o700 creates an ACL that can exclude the service
        # process; inherit the configured storage root's ACL instead.
        if os.name == 'nt':
            destination.parent.mkdir(parents=True, exist_ok=False)
        else:
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=False)
        with destination.open('xb') as handle:
            if os.name != 'nt':
                os.chmod(destination, 0o600)
            handle.write(content)
        scan(destination)
        try:
            pages = render(content, mime, kind)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else 'Не удалось прочитать файл.') from exc
        for index, page in enumerate(pages, 1):
            page_path = path(key, f'page-{index}.png')
            with page_path.open('xb') as handle:
                if os.name != 'nt':
                    os.chmod(page_path, 0o600)
                handle.write(page)
        return hashlib.sha256(content).hexdigest(), len(pages)
    except BaseException as exc:
        try:
            discard(key)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise HTTPException(503, 'Хранилище файлов временно недоступно. Обратитесь к администратору.') from exc
        raise


def discard(key: str) -> None:
    directory = path(key, 'original').parent
    if directory.exists():
        shutil.rmtree(directory)


def read(key: str, checksum: str, page: int | None = None) -> bytes:
    try:
        original = path(key, 'original').read_bytes()
        if hashlib.sha256(original).hexdigest() != checksum:
            raise HTTPException(404, 'Файл недоступен.')
        if page is None:
            return original
        # The service also verifies the immutable preview against its ledger digest.
        return path(key, f'page-{page}.png').read_bytes()
    except OSError as exc:
        raise HTTPException(404, 'Файл недоступен.') from exc
