"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from pyvista_build import cli


@pytest.fixture(autouse=True)
def _home_outside_tmp(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Point the home directory away from the temporary files, so paths print alike on every OS."""
    home = tmp_path_factory.mktemp('home')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))


@pytest.fixture(autouse=True)
def _no_job_summary(monkeypatch: pytest.MonkeyPatch):
    """Keep the GitHub job summary of a CI run out of the tests."""
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)


@pytest.fixture(autouse=True)
def _no_compiler_cache_env(monkeypatch: pytest.MonkeyPatch):
    """Keep the developer's compiler cache settings out of every test."""
    for name in (
        'CCACHE_BASEDIR',
        'CCACHE_COMPILERCHECK',
        'CCACHE_CONFIGPATH',
        'CCACHE_DIR',
        'CCACHE_LOGFILE',
        'CCACHE_NOHASHDIR',
        'SCCACHE_DIR',
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _plain_cli_console(monkeypatch: pytest.MonkeyPatch):
    """Print the CLI output plain and unwrapped, whatever the terminal and environment say."""
    monkeypatch.setattr(cli.APP, 'console', Console(force_terminal=False, width=4000))
    monkeypatch.setattr(
        cli.APP, 'error_console', Console(force_terminal=False, width=4000, stderr=True)
    )
