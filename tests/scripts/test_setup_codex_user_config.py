"""Tests for scripts/setup_codex_user_config.py (GitHub #76)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "setup_codex_user_config.py"


def _load():
    spec = importlib.util.spec_from_file_location("setup_codex_user_config", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["setup_codex_user_config"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def test_load_snippet_from_repo_example(mod):
    s = mod.load_snippet(REPO_ROOT)
    assert "[features]" in s
    assert "codex_hooks = true" in s


def test_merge_inserts_under_features(mod):
    body = "[features]\nfoo = 1\n"
    out = mod.merge_codex_hooks_into_existing(body)
    assert out is not None
    assert "codex_hooks = true" in out
    assert out.index("[features]") < out.index("codex_hooks")


def test_merge_noop_when_true(mod):
    body = "[features]\ncodex_hooks = true\n"
    assert mod.merge_codex_hooks_into_existing(body) is None


def test_merge_noop_when_false(mod):
    body = "[features]\ncodex_hooks = false\n"
    assert mod.merge_codex_hooks_into_existing(body) is None


def test_merge_appends_features_when_missing(mod):
    body = "other = 1\n"
    out = mod.merge_codex_hooks_into_existing(body)
    assert out is not None
    assert "[features]" in out
    assert "codex_hooks = true" in out


def test_apply_user_config_created(tmp_path, mod):
    p = tmp_path / "config.toml"
    snippet = "[features]\ncodex_hooks = true\n"
    assert mod.apply_user_config(p, snippet) == "created"
    assert p.read_text(encoding="utf-8") == snippet


def test_apply_user_config_idempotent(tmp_path, mod):
    p = tmp_path / "config.toml"
    snippet = "[features]\ncodex_hooks = true\n"
    mod.apply_user_config(p, snippet)
    assert mod.apply_user_config(p, snippet) == "already_enabled"
