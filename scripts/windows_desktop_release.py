#!/usr/bin/env python3
"""Scoped Windows x64 Desktop release; never impersonates the full release manifest."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
from pathlib import Path

if __package__:
    from . import collect_release_bundle as collector
    from . import release_publication as publication
else:
    import collect_release_bundle as collector
    import release_publication as publication

REPO = "GrothKeiran/webcodex-release"
MANIFEST = "webcodex-desktop-release-manifest.json"
PLATFORM = "win32-x64"
SCOPE = "windows-x64-desktop-only"
MAX_INSTALLER_BYTES = 512 * 1024 * 1024


def identity(version: str, tag: str, source_sha: str, repo: str, run_id: int, request_id: str) -> dict:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or tag != "v" + version:
        raise ValueError("Expected one canonical version and matching release tag")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("Expected an exact source commit")
    if repo != REPO or type(run_id) is not int or run_id <= 0:
        raise ValueError("Unexpected repository or workflow run id")
    if not re.fullmatch(r"rb_[0-9a-f]{24}", request_id):
        raise ValueError("Expected one durable build request id")
    return {"schema_version": 1, "scope": SCOPE, "platform": PLATFORM,
            "version": version, "tag": tag, "source_sha": source_sha, "repository": repo,
            "workflow_run_id": run_id, "request_id": request_id,
            "workflow_ref": f"{repo}/.github/workflows/release-build.yml@refs/tags/{tag}",
            "rust_target": "x86_64-pc-windows-msvc", "signing_mode": "unsigned"}


def installer_name(expected: dict) -> str:
    return f"webcodex-desktop-v{expected['version']}-{PLATFORM}-setup.exe"


def asset_names(expected: dict) -> set[str]:
    name = installer_name(expected)
    return {name, name + ".sha256", MANIFEST, "SHA256SUMS"}


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular release file: {path.name}")
    if path.stat().st_size <= 0 or path.stat().st_size > MAX_INSTALLER_BYTES:
        raise ValueError(f"Release file size is outside its bound: {path.name}")
    return collector.sha256_file(path)


def assemble(directory: Path, expected: dict, built_at: int) -> dict:
    name = installer_name(expected)
    if type(built_at) is not int or built_at <= 0:
        raise ValueError("Expected the annotated tag timestamp")
    if {p.name for p in directory.iterdir()} != {name, name + ".sha256"}:
        raise ValueError("Unexpected desktop candidate files; never mix artifacts")
    installer = directory / name
    value = digest(installer)
    sidecar = directory / (name + ".sha256")
    if sidecar.read_text(encoding="ascii") != f"{value}  {name}\n":
        raise ValueError("Installer checksum mismatch")
    # NSIS bootstrap itself may be x86. The installed Desktop and bundled
    # runtime PE architectures are independently fenced by the native smoke.
    with installer.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Installer is not a Windows executable")
    summary = {**expected, "built_at": built_at,
               "validation": "native-runtime-identity-and-pe;desktop-install-and-uninstall-smoke",
               "installer": {"filename": name, "size": installer.stat().st_size, "sha256": value}}
    (directory / MANIFEST).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    names = sorted(asset_names(expected) - {"SHA256SUMS"})
    (directory / "SHA256SUMS").write_text("".join(f"{digest(directory / n)}  {n}\n" for n in names), encoding="ascii")
    return verify(directory, expected)


def verify(directory: Path, expected: dict) -> dict:
    if {p.name for p in directory.iterdir()} != asset_names(expected):
        raise ValueError("Scoped bundle asset set mismatch")
    manifest_path = directory / MANIFEST
    if manifest_path.stat().st_size > 16 * 1024:
        raise ValueError("Scoped manifest exceeds its bound")
    summary = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict) or any(summary.get(k) != v for k, v in expected.items()):
        raise ValueError("Scoped manifest identity mismatch")
    if type(summary.get("built_at")) is not int or summary["built_at"] <= 0:
        raise ValueError("Invalid build timestamp")
    if summary.get("validation") != "native-runtime-identity-and-pe;desktop-install-and-uninstall-smoke":
        raise ValueError("Missing native Windows installation evidence")
    name = installer_name(expected)
    installer = directory / name
    value = digest(installer)
    if summary.get("installer") != {"filename": name, "size": installer.stat().st_size, "sha256": value}:
        raise ValueError("Scoped installer identity mismatch")
    with installer.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Installer is not a Windows executable")
    if (directory / (name + ".sha256")).read_text(encoding="ascii") != f"{value}  {name}\n":
        raise ValueError("Scoped installer checksum mismatch")
    sums = "".join(f"{digest(directory / n)}  {n}\n" for n in sorted(asset_names(expected) - {"SHA256SUMS"}))
    if (directory / "SHA256SUMS").read_text(encoding="ascii") != sums:
        raise ValueError("Scoped bundle checksum mismatch")
    return summary


def validate_run(run: dict, expected: dict) -> None:
    fields = {"id": expected["workflow_run_id"], "path": ".github/workflows/release-build.yml",
              "event": "workflow_dispatch", "head_sha": expected["source_sha"],
              "head_branch": expected["tag"], "status": "completed", "conclusion": "success",
              "display_title": f"Release build {expected['tag']} {expected['request_id']}"}
    if any(run.get(k) != v for k, v in fields.items()):
        raise ValueError("Candidate run does not match the successful exact-tag request")
    if run.get("repository", {}).get("full_name") != expected["repository"]:
        raise ValueError("Candidate run repository mismatch")


def collect(client: collector.GitHubClient, directory: Path, expected: dict) -> dict:
    run_id = expected["workflow_run_id"]
    run = client.fetch_json(f"/actions/runs/{run_id}")
    validate_run(run, expected)
    ref = client.fetch_json(f"/git/ref/tags/{expected['tag']}")
    if ref.get("object", {}).get("type") != "tag":
        raise ValueError("Release requires an annotated immutable tag")
    tag = client.fetch_json("/git/tags/" + ref["object"]["sha"])
    if (tag.get("tag") != expected["tag"] or tag.get("object", {}).get("sha") != expected["source_sha"]
            or tag.get("object", {}).get("type") != "commit"):
        raise ValueError("Immutable tag source mismatch")
    built_at = int(datetime.datetime.fromisoformat(tag["tagger"]["date"].replace("Z", "+00:00")).timestamp())
    listing = client.fetch_json(f"/actions/runs/{run_id}/artifacts?per_page=100")
    artifacts = listing.get("artifacts")
    if not isinstance(artifacts, list) or listing.get("total_count") != len(artifacts) or len(artifacts) > 10:
        raise ValueError("Artifact listing exceeds its bound")
    name = f"webcodex-desktop-v{expected['version']}-{PLATFORM}-bundle"
    matches = [a for a in artifacts if a.get("name") == name]
    if len(matches) != 1 or matches[0].get("expired") is not False:
        raise ValueError("Expected one live same-run scoped bundle")
    artifact = matches[0]
    if directory.exists():
        raise ValueError("Refusing to replace an existing collected bundle")
    directory.parent.mkdir(parents=True, exist_ok=True)
    archive = directory.parent / (directory.name + ".zip")
    client.download_artifact_zip(artifact["id"], archive, artifact["size_in_bytes"], collector._artifact_digest(artifact.get("digest")))
    collector.safe_extract_zip(archive, directory)
    summary = verify(directory, expected)
    if summary["built_at"] != built_at:
        raise ValueError("Scoped bundle tag timestamp mismatch")
    # Fail closed if a rerun changed the bound attempt during collection.
    refreshed = client.fetch_json(f"/actions/runs/{run_id}")
    validate_run(refreshed, expected)
    if refreshed.get("run_attempt") != run.get("run_attempt"):
        raise ValueError("Candidate attempt changed during collection")
    return summary


def verify_draft_assets(release: dict, directory: Path, expected: dict) -> dict:
    verify(directory, expected)
    if release.get("tag_name") != expected["tag"] or release.get("draft") is not True or release.get("prerelease") is not False:
        raise ValueError("Expected the exact unpublished non-prerelease draft")
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != 4:
        raise ValueError("Draft asset set mismatch")
    by_name = {a.get("name"): a for a in assets}
    if set(by_name) != asset_names(expected):
        raise ValueError("Draft asset names mismatch")
    for name, asset in by_name.items():
        if asset.get("state") != "uploaded" or asset.get("size") != (directory / name).stat().st_size:
            raise ValueError(f"Draft size/state mismatch: {name}")
        if publication._github_asset_digest(asset) != digest(directory / name):
            raise ValueError(f"Draft SHA-256 mismatch: {name}")
    return {"release_id": release["id"], "tag": expected["tag"], "scope": SCOPE, "verified_assets": sorted(by_name)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("assemble", "collect", "verify-draft"))
    parser.add_argument("--directory", type=Path, required=True)
    for name in ("version", "tag", "source-sha", "repo", "request-id"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--built-at", type=int)
    args = parser.parse_args()
    expected = identity(args.version, args.tag, args.source_sha, args.repo, args.run_id, args.request_id)
    if args.command == "assemble":
        result = assemble(args.directory, expected, args.built_at)
    else:
        client = collector.GitHubClient(args.repo, collector.resolve_github_token(), 60)
        if args.command == "collect":
            result = collect(client, args.directory, expected)
        else:
            release = publication._find_authenticated_release_by_tag(client, args.tag)
            result = verify_draft_assets(release, args.directory, expected)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
