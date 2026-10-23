"""Post-repair work on a wheel that the repair tools leave undone."""

from __future__ import annotations

import base64
import csv
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

_MACHO_MAGICS = (
    b'\xfe\xed\xfa\xce',
    b'\xfe\xed\xfa\xcf',
    b'\xce\xfa\xed\xfe',
    b'\xcf\xfa\xed\xfe',
    b'\xca\xfe\xba\xbe',
    b'\xca\xfe\xba\xbf',
)
_LIBRARY_SUFFIXES = ('.so', '.dylib')


class RepairError(Exception):
    """A wheel the post-repair work cannot handle."""


def is_macho(path: Path) -> bool:
    """Return whether a file starts with a Mach-O or universal binary magic number.

    Parameters
    ----------
    path : Path
        File to inspect.

    Returns
    -------
    bool
        ``True`` for a Mach-O file.

    """
    with path.open('rb') as handle:
        return handle.read(4) in _MACHO_MAGICS


def strip_wheel(wheel: Path) -> list[str]:
    """Strip the local symbols from every Mach-O library in a wheel and re-sign it ad-hoc.

    Parameters
    ----------
    wheel : Path
        Repaired wheel, rewritten in place with its ``RECORD`` recomputed.

    Returns
    -------
    list[str]
        Archive names of the libraries that were stripped.

    Raises
    ------
    RepairError
        When the wheel has no ``RECORD``.

    """
    with tempfile.TemporaryDirectory(prefix='pyvista-build-strip-') as tmp:
        tree = Path(tmp)
        with zipfile.ZipFile(wheel) as archive:
            infos = [i for i in archive.infolist() if not i.is_dir()]
            archive.extractall(tree)
        stripped = []
        for info in infos:
            member = tree / info.filename
            if member.suffix not in _LIBRARY_SUFFIXES or not is_macho(member):
                continue
            subprocess.run(['strip', '-x', str(member)], check=True)
            subprocess.run(['codesign', '--force', '--sign', '-', str(member)], check=True)
            stripped.append(info.filename)
        _rewrite_record(tree, infos)
        rewritten = tree / wheel.name
        with zipfile.ZipFile(rewritten, 'w', zipfile.ZIP_DEFLATED) as out:
            for info in infos:
                entry = zipfile.ZipInfo(info.filename, info.date_time)
                entry.external_attr = info.external_attr
                entry.compress_type = zipfile.ZIP_DEFLATED
                out.writestr(entry, (tree / info.filename).read_bytes())
        shutil.move(rewritten, wheel)
    return stripped


def _rewrite_record(tree: Path, infos: list[zipfile.ZipInfo]) -> None:
    """Recompute the hash and size of every ``RECORD`` line for the unpacked wheel."""
    record = next(
        (tree / i.filename for i in infos if i.filename.endswith('.dist-info/RECORD')), None
    )
    if record is None:
        msg = 'The repaired wheel has no RECORD, so it cannot be stripped and rewritten.'
        raise RepairError(msg)
    with record.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        for info in infos:
            member = tree / info.filename
            if member == record:
                writer.writerow([info.filename, '', ''])
                continue
            data = member.read_bytes()
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            writer.writerow([info.filename, f'sha256={digest}', len(data)])
