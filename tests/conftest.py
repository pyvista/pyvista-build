"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _home_outside_tmp(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Point the home directory away from the temporary files, so paths print alike on every OS."""
    home = tmp_path_factory.mktemp('home')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))


@pytest.fixture(autouse=True)
def _no_host_compiler(monkeypatch: pytest.MonkeyPatch):
    """Keep the host compiler out of every test: the smoke test passes unless a test patches it."""
    from pyvista_build import tools

    monkeypatch.setattr(tools, 'compiler_smoke_test', lambda *_, **__: None)


@pytest.fixture(autouse=True)
def _no_job_summary(monkeypatch: pytest.MonkeyPatch):
    """Keep the GitHub job summary of a CI run out of the tests."""
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
