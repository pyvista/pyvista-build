"""``pyvista-build BACKEND`` command line."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import sys
import types
import typing
from typing import Annotated
from typing import Any
from typing import Literal
from typing import NoReturn

from cyclopts import App
from cyclopts import Parameter
from cyclopts import validators
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from pyvista_build import BuildConfig
from pyvista_build import Builder
from pyvista_build import BuildError
from pyvista_build import ManifestError
from pyvista_build import __version__
from pyvista_build.manifest import MANIFEST_FILENAME
from pyvista_build.manifest import load_manifest
from pyvista_build.manylinux import default_image
from pyvista_build.phases import BUILD_TYPES
from pyvista_build.phases import COMPILER_CACHES
from pyvista_build.phases import BuildType
from pyvista_build.phases import CompilerCache
from pyvista_build.phases import short_path
from pyvista_build.registry import known_backends
from pyvista_build.registry import shipped_manifest
from pyvista_build.tools import default_python

#: Environment variable PyVista reads to pick its VTK backend; its value is the default backend.
BACKEND_ENV_VAR = 'PYVISTA_VTK_BACKEND'

APP = App(
    name='pyvista-build',
    help_format='md',
    version=f'pyvista-build {__version__}',
    help_on_error=True,
    usage='Usage: pyvista-build BACKEND [OPTIONS]',
    console=Console(),
    result_action='return_value',
)

#: The line for the ``--defaults`` set the current run applies, printed before the first step.
_defaults_line: list[str] = []


def print_error_and_exit(message: str, *, title: str = 'Error') -> NoReturn:
    """Print an error panel to stderr and exit with status 1.

    Parameters
    ----------
    message : str
        Error message to show in the panel.

    title : str, default: 'Error'
        Title of the panel.

    """
    panel = Panel(message, title=title, style='bold red', box=box.ROUNDED, title_align='left')
    APP.error_console.print(panel)
    raise SystemExit(1)


def _split_csv(values: list[str] | None) -> list[str]:
    """Flatten repeated and comma-separated values into one list."""
    return [item.strip() for value in values or [] for item in value.split(',') if item.strip()]


def _choices(values: tuple[str, ...]) -> str:
    """Join choices into an English list with an Oxford comma."""
    return f'{", ".join(values[:-1])}, or {values[-1]}'


_backend_help = (
    f'Backend to build: one of {", ".join(known_backends())}, or any name together with '
    f'``--url`` or ``--source``. Defaults to ``${BACKEND_ENV_VAR}`` when that is set.'
)


@APP.default
def build(
    backend: Annotated[str | None, Parameter(help=_backend_help)] = None,
    *,
    ref: Annotated[
        str | None,
        Parameter(
            help="Git tag, branch or commit to build. Defaults to the manifest's release tag."
        ),
    ] = None,
    source: Annotated[
        Path | None,
        Parameter(help='Existing source checkout to build instead of cloning.'),
    ] = None,
    url: Annotated[
        str | None,
        Parameter(help="Git URL to clone instead of the backend's own, such as a fork."),
    ] = None,
    with_: Annotated[
        list[str] | None,
        Parameter(
            name='--with', negative='', help='Groups to enable, comma-separated or repeated.'
        ),
    ] = None,
    without: Annotated[
        list[str] | None,
        Parameter(
            name='--without', negative='', help='Groups to disable, comma-separated or repeated.'
        ),
    ] = None,
    minimal: Annotated[
        bool, Parameter(negative='', help='Enable only the required groups.')
    ] = False,
    opt: Annotated[
        list[str] | None,
        Parameter(negative='', help='Set a manifest option, ``NAME=VALUE``. Repeatable.'),
    ] = None,
    build_type: Annotated[
        BuildType,
        Parameter(help=f'CMake build type: {_choices(BUILD_TYPES)}.'),
    ] = 'Release',
    jobs: Annotated[
        int | None,
        Parameter(
            validator=validators.Number(gte=1),
            help='Parallel compile jobs. Defaults to one per CPU core, at most one per 2 GB of '
            'memory.',
        ),
    ] = None,
    define: Annotated[
        list[str] | None,
        Parameter(
            name=['--define', '-D'],
            negative='',
            help='Extra CMake cache entry, ``KEY=VALUE``, applied last so it overrides the '
            'manifest.',
        ),
    ] = None,
    clean: Annotated[bool, Parameter(negative='', help='Delete the build tree first.')] = False,
    reconfigure: Annotated[
        bool, Parameter(negative='', help='Run cmake again even if the tree is configured.')
    ] = False,
    update: Annotated[
        bool,
        Parameter(
            negative='',
            help='Fetch, then check out ``--ref`` (or the release tag) in an existing checkout.',
        ),
    ] = False,
    compiler_cache: Annotated[
        CompilerCache,
        Parameter(
            help=f'Compiler cache: {_choices(COMPILER_CACHES)}. ``auto`` uses whichever is on '
            'PATH, ``none`` builds without one.'
        ),
    ] = 'auto',
    cache_dir: Annotated[
        Path | None,
        Parameter(
            help='Compiler cache directory. Defaults to '
            "``$CCACHE_DIR`` or ``$SCCACHE_DIR`` when set, else the cache tool's own default "
            'location, or ``<build-dir>/compiler-cache`` with ``--manylinux``.'
        ),
    ] = None,
    python: Annotated[
        Path | None,
        Parameter(
            help='Python to build the wheel for and install it into. Defaults to the active '
            'virtual environment, else ``.venv`` in the current directory, else the Python '
            'running the command.'
        ),
    ] = None,
    build_dir: Annotated[
        Path | None,
        Parameter(
            help='Where source, build tree, and wheels go. Defaults to ``./<backend>-build``.'
        ),
    ] = None,
    version_suffix: Annotated[
        str | None,
        Parameter(
            help='Wheel version suffix. Defaults to ``dev0+g<sha>``, or none when the '
            'checkout is at a tag.'
        ),
    ] = None,
    repair: Annotated[
        bool,
        Parameter(
            help='Bundle the libraries the wheel links against and tag it for other machines. '
            '``--no-repair`` skips it.'
        ),
    ] = True,
    install: Annotated[
        bool, Parameter(negative='', help='Install the built wheel into this environment.')
    ] = False,
    yes: Annotated[
        bool,
        Parameter(
            name=['--yes', '-y'],
            negative='',
            help='Start, and install what the build needs, without asking.',
        ),
    ] = False,
    manylinux: Annotated[
        bool,
        Parameter(
            negative='',
            help='Build inside a manylinux container through Docker, for a portable Linux wheel.',
        ),
    ] = False,
    manylinux_image: Annotated[
        str | None,
        Parameter(help='Container image for ``--manylinux``. Defaults to manylinux_2_28.'),
    ] = None,
    interactive: Annotated[
        bool,
        Parameter(
            name=['--interactive', '-i'],
            negative='',
            help='Walk through the steps, confirming each one before any command runs.',
        ),
    ] = False,
    dry_run: Annotated[
        bool, Parameter(negative='', help='Print the commands and run nothing.')
    ] = False,
    verbose: Annotated[
        bool,
        Parameter(
            name=['--verbose', '-v'],
            negative='',
            help=(
                'Print each command with its environment variables, and all of its output '
                'instead of one updating line.'
            ),
        ),
    ] = False,
    defaults: Annotated[
        str | None,
        Parameter(
            negative='',
            help="Apply the manifest's ``[defaults.NAME]`` set; the other options win over it.",
        ),
    ] = None,
) -> None:
    """Build a VTK backend wheel from source.

    Asks once before starting, then builds with the defaults and prints every command as it
    runs, with its output on one updating line (``--verbose`` prints all of it, and the
    environment variables each command sets). Anything the
    build has to install is listed before that question, which covers it. ``--yes`` answers
    it.
    ``--interactive`` walks through the steps, showing each setting and asking before running
    anything, and ``--dry-run`` prints the commands without running them. ``--manylinux``
    runs the build inside a manylinux container so the Linux wheel installs on any machine.
    """
    backend = _backend_name(backend)
    if source is not None and url is not None:
        print_error_and_exit('--source and --url are mutually exclusive.')
    if manylinux_image is not None and not manylinux:
        print_error_and_exit('--manylinux-image needs --manylinux.')
    if cache_dir is not None and compiler_cache == 'none':
        print_error_and_exit('--cache-dir has no effect with --compiler-cache none.')
    config = BuildConfig(
        backend=backend,
        build_dir=(build_dir or Path(f'{backend}-build')).resolve(),
        source=source.resolve() if source is not None else None,
        url=url,
        ref=ref,
        with_=_split_csv(with_),
        without=_split_csv(without),
        minimal=minimal,
        build_type=build_type,
        jobs=jobs,
        defines=define or [],
        options=opt or [],
        clean=clean,
        reconfigure=reconfigure,
        update=update,
        compiler_cache=compiler_cache,
        cache_dir=cache_dir.resolve() if cache_dir is not None else None,
        version_suffix=version_suffix,
        repair=repair,
        install=install,
        yes=yes,
        interactive=interactive,
        dry_run=dry_run,
        verbose=verbose,
        manylinux=(manylinux_image or default_image()) if manylinux else None,
        python=str(python.absolute()) if python is not None else default_python(),
    )
    for line in _defaults_line:
        APP.console.print(f'[dim]{escape(line)}[/dim]', highlight=False)
    try:
        Builder(config, console=APP.console).build()
    except (BuildError, ManifestError, OSError) as err:
        print_error_and_exit(escape(str(err)), title='PyVista build stopped')
    except (KeyboardInterrupt, EOFError):
        APP.console.print('\n[dim]Stopped.[/dim]')
        raise SystemExit(130) from None


def _backend_name(backend: str | None) -> str:
    """Return the backend to build, from the command line or the environment."""
    if backend is None:
        backend = os.environ.get(BACKEND_ENV_VAR)
        if not backend:
            msg = (
                f'Say which backend to build, e.g. `pyvista-build vtk`. '
                f'Known backends: {", ".join(known_backends())}.'
            )
            print_error_and_exit(msg)
    return 'vtk' if backend == 'vtkmodules' else backend


def _option_types() -> dict[str, tuple[Any, Parameter]]:
    """Return each ``build`` option's type and parameter, keyed by its name without dashes."""
    hints = typing.get_type_hints(build, include_extras=True)
    found: dict[str, tuple[Any, Parameter]] = {}
    for name, hint in hints.items():
        if name in ('backend', 'defaults', 'return'):
            continue
        type_, parameter = typing.get_args(hint)
        if typing.get_origin(type_) in (typing.Union, types.UnionType):
            (type_,) = [t for t in typing.get_args(type_) if t is not type(None)]
        found[name.removesuffix('_')] = (type_, parameter)
    return found


def _flag(key: str, parameter: Parameter) -> str:
    """Return the long command-line flag of an option."""
    names = parameter.name if isinstance(parameter.name, tuple) else (parameter.name,)
    long_names = [n for n in names if isinstance(n, str) and n.startswith('--')]
    return long_names[0] if long_names else f'--{key.replace("_", "-")}'


def expand_defaults(name: str, values: dict[str, Any], *, where: str, base: Path) -> list[str]:
    """Return the command-line tokens a ``[defaults.<name>]`` set stands for.

    Parameters
    ----------
    name : str
        Name of the set, for error messages.

    values : dict[str, Any]
        The set's keys and values as decoded from TOML.

    where : str
        Manifest file name, for error messages.

    base : Path
        Directory that relative paths in the set are resolved against.

    Returns
    -------
    list[str]
        Tokens to place before the user's own.

    """
    options = _option_types()
    tokens: list[str] = []
    for key, value in values.items():
        option = key.replace('-', '_')
        if option not in options:
            msg = (
                f'{where}: [defaults.{name}] has unknown key {key!r}; '
                f'the options are {", ".join(sorted(options))}.'
            )
            raise ManifestError(msg)
        type_, parameter = options[option]
        flag = _flag(option, parameter)
        expected = _expected(type_)
        if type_ is bool:
            if not isinstance(value, bool):
                _wrong_type(name, key, value, expected, where=where)
            if value:
                tokens.append(flag)
            elif parameter.negative != ():
                tokens.append(f'--no-{flag[2:]}')
        elif typing.get_origin(type_) is list:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                _wrong_type(name, key, value, expected, where=where)
            tokens.extend(token for item in value for token in (flag, item))
        elif type_ is int:
            if isinstance(value, bool) or not isinstance(value, int):
                _wrong_type(name, key, value, expected, where=where)
            tokens.extend((flag, str(value)))
        else:
            choices = typing.get_args(type_) if typing.get_origin(type_) is Literal else ()
            if not isinstance(value, str) or (choices and value not in choices):
                _wrong_type(name, key, value, expected, where=where)
            tokens.extend((flag, str(base / value) if type_ is Path else value))
    return tokens


def _expected(type_: Any) -> str:
    """Describe the TOML value an option takes."""
    if type_ is bool:
        return 'true or false'
    if typing.get_origin(type_) is list:
        return 'a list of strings'
    if type_ is int:
        return 'an integer'
    if type_ is Path:
        return 'a path'
    if typing.get_origin(type_) is Literal:
        return f'one of {", ".join(map(repr, typing.get_args(type_)))}'
    return 'a string'


def _wrong_type(name: str, key: str, value: Any, expected: str, *, where: str) -> NoReturn:
    """Raise for a set value of the wrong type."""
    msg = f'{where}: [defaults.{name}] {key} must be {expected}, not {value!r}.'
    raise ManifestError(msg)


def describe_defaults(name: str, values: dict[str, Any], *, where: str) -> str:
    """Return the line printed for an applied set, such as ``Defaults ci from x.toml: yes``.

    Parameters
    ----------
    name : str
        Name of the set.

    values : dict[str, Any]
        The set's keys and values.

    where : str
        Manifest file name.

    Returns
    -------
    str
        The line.

    """
    items = []
    for key, value in values.items():
        if value is True:
            items.append(key)
        elif isinstance(value, list):
            items.append(f'{key}={",".join(value)}')
        else:
            items.append(f'{key}={str(value).lower() if isinstance(value, bool) else value}')
    return f'Defaults {name} from {where}: {", ".join(items)}'


def _defaults_manifest(backend: str, source: Path | None) -> Path:
    """Return the manifest ``--defaults`` reads: checkout, current directory, else shipped."""
    candidates = [Path.cwd() / MANIFEST_FILENAME]
    if source is not None:
        candidates.insert(0, source / MANIFEST_FILENAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    shipped = shipped_manifest(backend)
    if shipped is not None:
        return shipped
    looked = ' or '.join(short_path(c.parent) for c in candidates)
    msg = (
        f'--defaults needs a {MANIFEST_FILENAME}: none in {looked}, and none is shipped for '
        f'{backend!r}.'
    )
    raise ManifestError(msg)


def _user_options(tokens: list[str]) -> set[str]:
    """Return the options the user's own tokens name, by any of their flags."""
    flags: dict[str, str] = {}
    for key, (_, parameter) in _option_types().items():
        names = parameter.name if isinstance(parameter.name, tuple) else (parameter.name,)
        for flag in [*(n for n in names if isinstance(n, str)), _flag(key, parameter)]:
            flags[flag] = key
            if flag.startswith('--'):
                flags[f'--no-{flag[2:]}'] = key
    named = set()
    for token in tokens:
        if token == '--':
            break
        if token.startswith('-') and token.split('=', 1)[0] in flags:
            named.add(flags[token.split('=', 1)[0]])
    return named


def _defaults_tokens(
    name: str,
    backend: str,
    source: Path | None,
    user_tokens: list[str],
    user_groups: tuple[list[str], list[str]],
) -> list[str]:
    """Expand the named set without the options the command line names."""
    path = _defaults_manifest(backend, source)
    manifest = load_manifest(path)
    where = short_path(path)
    if name not in manifest.defaults:
        available = (
            f'the sets are {", ".join(manifest.defaults)}'
            if manifest.defaults
            else 'it defines no sets'
        )
        msg = f'{where} has no [defaults.{name}]; {available}.'
        raise ManifestError(msg)
    values = manifest.defaults[name]
    expand_defaults(name, values, where=where, base=path.parent)
    _defaults_line.append(describe_defaults(name, values, where=where))
    named = _user_options(user_tokens)
    kept = {
        key.replace('-', '_'): value
        for key, value in values.items()
        if key.replace('-', '_') not in named or isinstance(value, list)
    }
    with_, without = user_groups
    for key, other in (('with', without), ('without', with_)):
        if key in kept:
            kept[key] = [group for group in kept[key] if group not in other]
    return expand_defaults(name, kept, where=where, base=path.parent)


def _utf8_streams() -> None:
    """Switch stdout and stderr to UTF-8 so the progress output survives a cp1252 console."""
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, 'encoding', None) or '').lower().replace('-', '')
        if encoding != 'utf8' and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')


def main(argv: list[str] | str | None = None) -> None:
    """Run the command line, expanding the ``--defaults`` set first.

    Parameters
    ----------
    argv : list[str] | str, optional
        Command-line arguments. Defaults to ``sys.argv[1:]``.

    """
    _utf8_streams()
    if isinstance(argv, str):
        argv = shlex.split(argv, posix=os.name != 'nt')
    _, bound, _ = APP.parse_args(argv)
    name = bound.arguments.get('defaults')
    _defaults_line.clear()
    if name is not None:
        if not name.strip() or ',' in name:
            print_error_and_exit('--defaults takes one set name.')
        backend = _backend_name(bound.arguments.get('backend'))
        user_tokens = list(argv if argv is not None else sys.argv[1:])
        groups = (
            _split_csv(bound.arguments.get('with_')),
            _split_csv(bound.arguments.get('without')),
        )
        try:
            tokens = _defaults_tokens(
                name, backend, bound.arguments.get('source'), user_tokens, groups
            )
        except ManifestError as err:
            print_error_and_exit(escape(str(err)))
        argv = tokens + user_tokens
    APP(tokens=argv)
