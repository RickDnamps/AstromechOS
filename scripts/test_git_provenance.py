#!/usr/bin/env python3
"""Unit tests for shared/git_provenance.py — the DNA paternity check.

Strategy:
  - We build TEMP git repos (one "real fork" cloning our local repo, one
    "unrelated" with a single fresh commit) and run the validator against
    them. No network needed — uses `file://` URLs of the temp repos.
  - The local AstromechOS repo (this checkout) IS a descendant of the
    official initial commit by definition (it IS the official lineage),
    so we use it as the repo_path inside which the fetch happens.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from shared import git_provenance as G   # noqa: E402


def _run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          timeout=60, env=env or os.environ)


def _local_repo_url() -> str:
    """file:// URL of the LOCAL repo's .git directory — used as a stand-in
    for "a legitimate fork" in tests. Avoids the `git clone --bare` step
    that triggers Windows file-locking on a live working tree."""
    git_dir = REPO / '.git'
    if not git_dir.is_dir():
        raise RuntimeError(f'local .git not found: {git_dir}')
    return git_dir.as_uri()


def _make_unrelated_repo() -> tuple[Path, str]:
    """Create a tiny fresh repo with one commit, no shared history with us.
    Returns (path_to_bare_repo, file_url_for_git)."""
    td = Path(tempfile.mkdtemp(prefix='astro-prov-alien-'))
    work = td / 'work'
    work.mkdir()
    env = os.environ.copy()
    env['GIT_AUTHOR_NAME']    = 'test'
    env['GIT_AUTHOR_EMAIL']   = 'test@example.com'
    env['GIT_COMMITTER_NAME']  = 'test'
    env['GIT_COMMITTER_EMAIL'] = 'test@example.com'
    _run(['git', 'init', '-b', 'main'], cwd=work, env=env)
    (work / 'README.md').write_text('totally unrelated')
    _run(['git', 'add', '.'], cwd=work, env=env)
    _run(['git', 'commit', '-m', 'unrelated init'], cwd=work, env=env)
    bare = td / 'alien.git'
    r = _run(['git', 'clone', '--bare', str(work), str(bare)], cwd=td, env=env)
    if r.returncode != 0:
        raise RuntimeError(f'alien bare clone failed: {r.stderr}')
    return bare, bare.as_uri()


class TestConstants(unittest.TestCase):
    def test_anchor_sha_format(self):
        self.assertEqual(len(G.OFFICIAL_INITIAL_COMMIT), 40)
        self.assertRegex(G.OFFICIAL_INITIAL_COMMIT, r'^[0-9a-f]{40}$')

    def test_official_url_set(self):
        self.assertTrue(G.OFFICIAL_REPO_URL.startswith('https://github.com/'))
        self.assertIn('AstromechOS', G.OFFICIAL_REPO_URL)


class TestRemoteExists(unittest.TestCase):
    def test_rejects_empty(self):
        ok, _ = G.validate_remote_exists('')
        self.assertFalse(ok)

    def test_rejects_non_string(self):
        ok, _ = G.validate_remote_exists(None)         # type: ignore[arg-type]
        self.assertFalse(ok)

    def test_rejects_bad_scheme(self):
        ok, why = G.validate_remote_exists('javascript:alert(1)')
        self.assertFalse(ok)
        self.assertIn('scheme', why.lower())

    def test_rejects_unreachable_local_path(self):
        ok, _ = G.validate_remote_exists('file:///__nope__/missing.git')
        self.assertFalse(ok)

    def test_accepts_local_repo_via_file_url(self):
        ok, why = G.validate_remote_exists(_local_repo_url())
        self.assertTrue(ok, why)


class TestPaternity(unittest.TestCase):
    def test_passes_for_local_repo_lineage(self):
        """Pointing the validator at our OWN .git as the 'candidate URL'
        means the fetch brings in our own main, which IS the official
        lineage by definition — paternity must pass."""
        ok, why = G.validate_paternity(str(REPO), _local_repo_url(),
                                       branch='main', timeout=30)
        self.assertTrue(ok, why)
        self.assertIn('DNA OK', why)

    def test_rejects_unrelated_repo(self):
        """A freshly-init'd repo with its own initial commit shares NO
        history with the official AstromechOS — paternity must FAIL."""
        bare, url = _make_unrelated_repo()
        try:
            ok, why = G.validate_paternity(str(REPO), url, branch='main', timeout=30)
            self.assertFalse(ok, f'unrelated repo was accepted: {why}')
            self.assertIn('DNA FAIL', why)
        finally:
            shutil.rmtree(bare.parent, ignore_errors=True)

    def test_rejects_bad_branch_name(self):
        ok, why = G.validate_paternity(str(REPO), G.OFFICIAL_REPO_URL,
                                       branch='--upload-pack=/tmp/pwn')
        self.assertFalse(ok)
        self.assertIn('branch', why.lower())

    def test_rejects_non_repo_path(self):
        with tempfile.TemporaryDirectory() as td:
            ok, why = G.validate_paternity(td, G.OFFICIAL_REPO_URL, branch='main')
            self.assertFalse(ok)
            self.assertIn('git', why.lower())


class TestRepoUrlComposite(unittest.TestCase):
    def test_validate_repo_url_delegates_to_paternity(self):
        # Just a smoke test that the composite returns the same shape.
        ok, why = G.validate_repo_url(str(REPO), '', branch='main')
        self.assertFalse(ok)
        self.assertIsInstance(why, str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
