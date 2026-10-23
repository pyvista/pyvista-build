"""Run the build inside a manylinux container so the Linux wheel is portable."""

from __future__ import annotations

import fnmatch
from importlib.metadata import requires
import os
from pathlib import Path
import platform
import shlex
from typing import TYPE_CHECKING

from packaging.requirements import Requirement

if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Mapping
    from collections.abc import Sequence

POLICY = 'manylinux_2_28'
IMAGES = {arch: f'quay.io/pypa/{POLICY}_{arch}' for arch in ('x86_64', 'aarch64')}
#: Set by the pypa images to the platform tag auditwheel should produce.
PLAT_VAR = 'AUDITWHEEL_PLAT'
WORK = '/work'
SOURCE = '/src'
CACHE = '/cache'
PACKAGE_ROOT = '/opt/pyvista-build-host'
SUMMARY = '/github-step-summary.md'
PIP_CACHE = f'{WORK}/pip-cache'
CCACHE_VERSION = '4.14'
CCACHE_SHA256 = {
    'x86_64': '888eaf9697919d6eba77be797e9d9c9e40e734d11d67d25a79b075c3f79f6c77',
    'aarch64': '40623f11012a97d60c7d90058d7e3c8c70a3802af53a34067b89e6345c89db69',
}
DOCKER_INSTRUCTIONS = 'Install Docker: https://docs.docker.com/get-docker/'
_HOST_PATH_VARS = frozenset(
    {'CCACHE_BASEDIR', 'CCACHE_CONFIGPATH', 'CCACHE_DIR', 'CCACHE_LOGFILE', 'SCCACHE_DIR'}
)
#: Cache size the build inside the container sets when the host did not set ``CCACHE_MAXSIZE``.
CCACHE_MAXSIZE = '30G'
#: Container paths the build uses itself, so ``--mount`` cannot take them.
RESERVED_PATHS = (WORK, SOURCE, CACHE, SUMMARY, PACKAGE_ROOT)
#: Terminal color settings the build inside the container follows as well.
COLOR_VARS = ('FORCE_COLOR', 'NO_COLOR', 'TERM', 'COLUMNS')


def host_arch() -> str:
    """Return the container architecture matching this machine.

    Returns
    -------
    str
        ``'x86_64'`` or ``'aarch64'``.

    """
    machine = platform.machine().lower()
    return 'aarch64' if machine in ('arm64', 'aarch64') else 'x86_64'


def default_image() -> str:
    """Return the manylinux image for this machine's architecture.

    Returns
    -------
    str
        Image reference.

    """
    return IMAGES[host_arch()]


def container_plat() -> str:
    """Return the platform tag the repair inside the container asks auditwheel for.

    Returns
    -------
    str
        ``AUDITWHEEL_PLAT`` as the image sets it, else the default policy for this architecture.

    """
    return os.environ.get(PLAT_VAR) or f'{POLICY}_{host_arch()}'


def container_python(version: tuple[int, int], abiflags: str = '') -> str:
    """Return the interpreter inside the image that matches a Python build.

    Parameters
    ----------
    version : tuple[int, int]
        Major and minor version of the interpreter the wheel is built for.

    abiflags : str, default: ''
        Its ``sys.abiflags``; ``t`` selects the free-threaded build.

    Returns
    -------
    str
        Path such as ``/opt/python/cp314-cp314/bin/python``, or ``cp314-cp314t`` on a
        free-threaded build.

    """
    tag = f'cp{version[0]}{version[1]}'
    abi = tag + ('t' if 't' in abiflags else '')
    return f'/opt/python/{tag}-{abi}/bin/python'


def package_dir() -> Path:
    """Return the directory of the running ``pyvista_build`` package.

    Returns
    -------
    Path
        Package directory, mounted read-only into the container.

    """
    return Path(__file__).resolve().parent


def requirements() -> list[str]:
    """Return this package's runtime requirements, without the optional extras.

    Returns
    -------
    list[str]
        Requirement strings for ``pip install`` inside the container.

    """
    names = requires('pyvista-build') or []
    return [r for r in names if 'extra' not in str(Requirement(r).marker or '')]


def container_script(
    *,
    python: str,
    packages: Sequence[str],
    requirements: Sequence[str],
    config: str,
    ccache: bool,
    owner: str | None,
    paths: Sequence[str],
    quiet: bool = False,
) -> str:
    """Return the shell script the container runs.

    Parameters
    ----------
    python : str
        Interpreter inside the image.

    packages : Sequence[str]
        System packages to install with ``dnf`` or ``yum``.

    requirements : Sequence[str]
        Python packages this package needs at run time.

    config : str
        JSON build configuration passed to ``python -m pyvista_build``.

    ccache : bool
        Whether to install a static ``ccache``.

    owner : str or None
        ``uid:gid`` to hand the written files back to, or ``None`` to leave them.

    paths : Sequence[str]
        Mounted directories to hand back.

    quiet : bool, default: False
        Install system packages without listing each one.

    Returns
    -------
    str
        Bash script.

    """
    lines = ['set -euo pipefail']
    if owner is not None and paths:
        lines.append(f"trap 'chown -R {owner} {' '.join(paths)} || true' EXIT")
    lines += [
        f'PY={shlex.quote(python)}',
        'if ! test -x "$PY"; then echo "$PY is not in this image" >&2; exit 1; fi',
        "git config --global --add safe.directory '*'",
        f'export PIP_CACHE_DIR={PIP_CACHE}',
        'mkdir -p "$PIP_CACHE_DIR" && chown "$(id -u):$(id -g)" "$PIP_CACHE_DIR"',
    ]
    if packages:
        pkgs = ' '.join(shlex.quote(p) for p in packages)
        flags = '-y -q' if quiet else '-y'
        lines.append(
            'if command -v dnf >/dev/null; then '
            f'dnf install {flags} --setopt=install_weak_deps=False {pkgs}; '
            f'else yum install {flags} {pkgs}; fi'
        )
    if ccache:
        name = f'ccache-{CCACHE_VERSION}-linux-$ARCH-musl-static'
        url = f'https://github.com/ccache/ccache/releases/download/v{CCACHE_VERSION}/{name}.tar.xz'
        cases = ' '.join(f'{arch}) SHA={sha};;' for arch, sha in CCACHE_SHA256.items())
        lines += [
            'ARCH=$(uname -m)',
            f'case "$ARCH" in {cases} *) echo "no static ccache for $ARCH" >&2; exit 1;; esac',
            f'curl -sSfL -o /tmp/ccache.tar.xz "{url}"',
            'echo "$SHA  /tmp/ccache.tar.xz" | sha256sum --check --quiet',
            f'tar -xJf /tmp/ccache.tar.xz -C /usr/local/bin --strip-components=1 "{name}/ccache"',
        ]
    reqs = ' '.join(shlex.quote(r) for r in requirements)
    lines += [
        f'"$PY" -m pip install --quiet --root-user-action=ignore --only-binary :all: {reqs}',
        f'PYTHONPATH={PACKAGE_ROOT} "$PY" -m pyvista_build {shlex.quote(config)}',
    ]
    return '\n'.join(lines)


def parse_mount(spec: str) -> tuple[Path, str, bool]:
    """Split a ``--mount HOST:CONTAINER[:ro]`` value.

    Parameters
    ----------
    spec : str
        Host path, an absolute container path, and an optional ``ro`` mode, colon-separated.
        A Windows drive letter in the host path is kept.

    Returns
    -------
    Path
        Host path.

    str
        Container path.

    bool
        Whether the mount is read-only.

    Raises
    ------
    ValueError
        When the value has no absolute container path or names a path the build uses.

    """
    read_only = spec.endswith(':ro')
    body = spec[:-3] if read_only else spec
    host, sep, inside = body.rpartition(':')
    if not sep or not host or not inside.startswith('/'):
        msg = (
            f'--mount takes HOST:CONTAINER[:ro], an absolute container path with ro the only '
            f'mode, not {spec!r}.'
        )
        raise ValueError(msg)
    inside = inside.rstrip('/') or '/'
    if inside == '/' or any(
        inside == p or inside.startswith(f'{p}/') or p.startswith(f'{inside}/')
        for p in RESERVED_PATHS
    ):
        msg = f'--mount cannot use {inside}: the build mounts {", ".join(RESERVED_PATHS)} itself.'
        raise ValueError(msg)
    return Path(host), inside, read_only


def docker_command(
    image: str,
    *,
    mounts: Mapping[str, Path],
    script: str,
    interactive: bool,
    env: Mapping[str, str],
    passthrough: Sequence[str] = (),
    read_only: Collection[str] = (),
) -> list[str]:
    """Assemble the ``docker run`` command.

    Parameters
    ----------
    image : str
        Image to run.

    mounts : Mapping[str, Path]
        Container path to host directory. This package is mounted read-only.

    script : str
        Script passed to ``bash -c`` inside the container.

    interactive : bool
        Attach a terminal so the build inside can ask questions.

    env : Mapping[str, str]
        Host environment; its non-path ``CCACHE_*`` and ``SCCACHE_*`` settings pass through.

    passthrough : Sequence[str]
        Names or ``fnmatch`` patterns of further variables to pass through.

    read_only : Collection[str]
        Container paths among ``mounts`` to mount read-only.

    Returns
    -------
    list[str]
        Command and arguments.

    """
    cmd = ['docker', 'run', '--rm', '--init', '-i']
    if interactive:
        cmd.append('-t')
    for inside, outside in mounts.items():
        mode = ':ro' if inside.startswith(PACKAGE_ROOT) or inside in read_only else ''
        cmd += ['--volume', f'{outside}:{inside}{mode}']
    for name in sorted(env):
        cache = name.startswith(('CCACHE_', 'SCCACHE_'))
        listed = any(fnmatch.fnmatchcase(name, pattern) for pattern in passthrough)
        if name in COLOR_VARS or ((cache or listed) and name not in _HOST_PATH_VARS):
            cmd += ['--env', name]
    if SUMMARY in mounts:
        cmd += ['--env', f'GITHUB_STEP_SUMMARY={SUMMARY}']
    cmd += ['--workdir', WORK, image, 'bash', '-c', script]
    return cmd


def file_owner() -> str | None:
    """Return ``uid:gid`` of the current user, or ``None`` where that has no meaning.

    Returns
    -------
    str or None
        Owner spec for ``chown``.

    """
    getuid = getattr(os, 'getuid', None)
    getgid = getattr(os, 'getgid', None)
    if getuid is None or getgid is None:
        return None
    return f'{getuid()}:{getgid()}'
