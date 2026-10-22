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
def _no_job_summary(monkeypatch: pytest.MonkeyPatch):
    """Keep the GitHub job summary of a CI run out of the tests."""
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
