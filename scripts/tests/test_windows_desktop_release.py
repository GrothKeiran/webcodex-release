from __future__ import annotations

import copy
import json
import os
import zipfile
from unittest import mock
import tempfile
import unittest
from pathlib import Path

from scripts import windows_desktop_release as release


class WindowsDesktopReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected = release.identity("0.5.0", "v0.5.0", "a" * 40, release.REPO, 123, "rb_" + "b" * 24)
        self.name = release.installer_name(self.expected)
        installer = self.root / self.name
        installer.write_bytes(b"MZsynthetic-nsis-test-fixture")
        (self.root / (self.name + ".sha256")).write_text(f"{release.digest(installer)}  {self.name}\n")

    def assembled(self):
        return release.assemble(self.root, self.expected, 1700000000)

    def test_scoped_bundle_contains_only_desktop_and_scoped_provenance(self):
        summary = self.assembled()
        self.assertEqual(summary["platform"], "win32-x64")
        self.assertEqual(summary["scope"], release.SCOPE)
        self.assertEqual({p.name for p in self.root.iterdir()}, release.asset_names(self.expected))
        self.assertFalse((self.root / "webcodex-release-manifest.json").exists())
        self.assertEqual(release.verify(self.root, self.expected), summary)

    def test_rejects_wrong_repository_version_or_request(self):
        for kwargs in ({"repo": "yyjeqhc/webcodex"}, {"version": "0.5.1"}, {"source_sha": "short"},
                       {"run_id": 0}, {"request_id": "manual"}):
            args = {"version": "0.5.0", "tag": "v0.5.0", "source_sha": "a" * 40,
                    "repo": release.REPO, "run_id": 123, "request_id": "rb_" + "b" * 24, **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                release.identity(**args)

    def test_rejects_extra_platform_candidate(self):
        (self.root / "arm64.exe").write_bytes(b"MZarm")
        with self.assertRaises(ValueError):
            self.assembled()

    def test_rejects_corrupt_candidate_checksum(self):
        (self.root / (self.name + ".sha256")).write_text("0" * 64 + "  " + self.name + "\n")
        with self.assertRaises(ValueError):
            self.assembled()

    def test_rejects_manifest_source_or_scope_drift(self):
        self.assembled()
        path = self.root / release.MANIFEST
        original = path.read_text()
        for key, value in (("platform", "win32-arm64"), ("source_sha", "c" * 40),
                           ("workflow_run_id", 124), ("scope", "all")):
            manifest = json.loads(original)
            manifest[key] = value
            path.write_text(json.dumps(manifest))
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.verify(self.root, self.expected)
        path.write_text(original)

    @unittest.skipIf(os.name == "nt", "symlink fixture requires POSIX")
    def test_rejects_tampered_installer_or_symlink(self):
        self.assembled()
        path = self.root / self.name
        original = path.read_bytes()
        path.write_bytes(original + b"tamper")
        with self.assertRaises(ValueError):
            release.verify(self.root, self.expected)
        path.unlink()
        other = self.root.parent / (self.root.name + "-outside.exe")
        self.addCleanup(other.unlink, missing_ok=True)
        other.write_bytes(original)
        path.symlink_to(other)
        with self.assertRaises(ValueError):
            release.verify(self.root, self.expected)

    def test_run_identity_fails_closed(self):
        run = {"id": 123, "path": ".github/workflows/release-build.yml", "event": "workflow_dispatch",
               "head_sha": "a" * 40, "head_branch": "v0.5.0", "status": "completed", "conclusion": "success",
               "display_title": "Release build v0.5.0 rb_" + "b" * 24,
               "repository": {"full_name": release.REPO}}
        release.validate_run(run, self.expected)
        for key, value in (("id", 124), ("head_sha", "c" * 40), ("head_branch", "main"),
                           ("conclusion", "failure"), ("display_title", "another request")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.validate_run({**run, key: value}, self.expected)

    def test_draft_assets_require_exact_names_sizes_and_digests(self):
        self.assembled()
        assets = [{"name": name, "state": "uploaded", "size": (self.root / name).stat().st_size,
                   "digest": "sha256:" + release.digest(self.root / name)}
                  for name in sorted(release.asset_names(self.expected))]
        draft = {"id": 789, "tag_name": "v0.5.0", "draft": True, "prerelease": False, "assets": assets}
        self.assertEqual(release.verify_draft_assets(draft, self.root, self.expected)["release_id"], 789)
        for key, value in (("digest", "sha256:" + "0" * 64), ("size", 0), ("name", "arm64.exe")):
            broken = copy.deepcopy(draft)
            broken["assets"][0][key] = value
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)):
                release.verify_draft_assets(broken, self.root, self.expected)

    def test_collect_binds_same_run_tag_artifact_digest_and_bytes(self):
        summary = self.assembled()
        directory = self.root / "collected"
        archive = self.root / "fixture.zip"
        with zipfile.ZipFile(archive, "w") as output:
            for name in release.asset_names(self.expected):
                output.write(self.root / name, name)
        value = release.digest(archive)
        run = {"id": 123, "path": ".github/workflows/release-build.yml", "event": "workflow_dispatch",
               "head_sha": "a" * 40, "head_branch": "v0.5.0", "status": "completed", "conclusion": "success",
               "run_attempt": 1, "display_title": "Release build v0.5.0 rb_" + "b" * 24,
               "repository": {"full_name": release.REPO}}
        payloads = {
            "/actions/runs/123": run,
            "/git/ref/tags/v0.5.0": {"object": {"type": "tag", "sha": "d" * 40}},
            "/git/tags/" + "d" * 40: {"tag": "v0.5.0", "object": {"type": "commit", "sha": "a" * 40},
                                      "tagger": {"date": "2023-11-14T22:13:20Z"}},
            "/actions/runs/123/artifacts?per_page=100": {"total_count": 1, "artifacts": [
                {"name": "webcodex-desktop-v0.5.0-win32-x64-bundle", "id": 456, "expired": False,
                 "size_in_bytes": archive.stat().st_size, "digest": "sha256:" + value}]},
        }
        client = mock.Mock()
        client.fetch_json.side_effect = lambda path: payloads[path]
        def download(artifact_id, path, size, expected_digest):
            self.assertEqual((artifact_id, size, expected_digest), (456, archive.stat().st_size, value))
            path.write_bytes(archive.read_bytes())
        client.download_artifact_zip.side_effect = download
        self.assertEqual(release.collect(client, directory, self.expected), summary)
        with self.assertRaises(ValueError):
            release.collect(client, directory, self.expected)

    def test_build_workflow_keeps_default_full_release_and_scopes_windows_explicitly(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / ".github/workflows/release-build.yml").read_text()
        self.assertIn("windows_desktop_only:", text)
        for job in ("linux", "macos"):
            self.assertIn(f"  {job}:\n    if: ${{{{ !inputs.windows_desktop_only }}}}", text)
        self.assertIn("matrix: ${{ fromJSON(needs.prepare.outputs.windows_matrix) }}", text)
        self.assertIn("always() && !inputs.windows_desktop_only &&", text)
        self.assertIn("desktop_install_windows_smoke.ps1", text)
        self.assertIn("Build and verify native Windows candidate", text)
        control = (root / ".github/workflows/fork-windows-desktop.yml").read_text()
        self.assertIn("readiness-start", control)
        self.assertIn("windows_desktop_only=true", control)
        self.assertIn("--verify-tag --draft", control)
        self.assertLess(control.index("verify-draft"), control.index("-F draft=false"))
        self.assertNotIn("--clobber", control)


if __name__ == "__main__":
    unittest.main()
