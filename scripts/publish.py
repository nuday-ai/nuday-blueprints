#!/usr/bin/env python3
"""Build the whole signed catalog site from this repository, in one step.

    uv run python scripts/publish.py --key <release key PEM> [--out _site]
                                     [--published https://.../v1/index.json]

1. Every official blueprint (``blueprints/<name>/blueprint.yaml``) is validated,
   packed and signed with the release key.
2. Every merged partner submission (``submissions/**/*.json``) is validated and
   counter-signed: merging its pull request IS the review (CODEOWNERS makes the
   platform team's approval required for ``submissions/``).
3. The index is built from those files (serial = the current Unix time, so every
   run is higher than the last), signed, and verified again from the output.

Nothing is committed back: the output directory is the whole site, rebuilt from
source every run. The Publish workflow runs this on every merge to main and
weekly, so the index never gets close to expiring.

``--published`` compares against the live index: a name and version already
published with DIFFERENT content fails the run (bump ``metadata.version``).
Pull requests run this with a throwaway key (``--dry-run-key``) to prove the
publish would succeed without ever seeing the real key.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from nuday.blueprints import index as I
from nuday.blueprints import layout as L
from nuday.blueprints import signing as S

ROOT = Path(__file__).resolve().parent.parent


def nuday(*args: str) -> str:
    """Run the nuday CLI; any failure stops the publish with its output."""
    proc = subprocess.run(["nuday", "blueprint", *args], capture_output=True, text=True)
    out = "\n".join(line for line in (proc.stdout + proc.stderr).splitlines() if not line.startswith("av ·"))
    if proc.returncode != 0:
        sys.exit(f"nuday blueprint {' '.join(args)} failed:\n{out}")
    return out


def packed_facts(path: Path) -> tuple[str, str, str]:
    """(name, version, content hash) of a packed blueprint file."""
    packed = L.as_packed(json.loads(path.read_text(encoding="utf-8")))
    meta = (packed.get("blueprint") or {}).get("metadata") or {}
    return str(meta.get("name")), str(meta.get("version")), L.content_sha256(packed)


def key_kid(pem_path: Path) -> str:
    private = S.load_private_key_pem(pem_path.read_bytes())
    return S.kid_for(S.public_key_b64(private))


def fetch_published(url: str) -> dict[tuple[str, str], str]:
    """{(name, version): content hash} of the live index; empty when there is none yet."""
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - our own catalog URL
            doc = json.loads(resp.read())
    except Exception as e:  # noqa: BLE001 - first publish: nothing live yet
        print(f"No published index at {url} ({e}); skipping the version check.")
        return {}
    out = {}
    for listing in (doc.get("index") or {}).get("listings") or []:
        for v in listing.get("versions") or []:
            out[(listing["name"], v["version"])] = v["content_sha256"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    keys = ap.add_mutually_exclusive_group(required=True)
    keys.add_argument("--key", type=Path, help="The release key PEM (must match RELEASE_KID)")
    keys.add_argument("--dry-run-key", action="store_true",
                      help="Sign with a throwaway key instead (pull requests): proves the build, publishes nothing")
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    ap.add_argument("--published", help="URL of the live index, for the version-bump check")
    ap.add_argument("--expires-days", type=int, default=30)
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="nuday-catalog-"))
    if args.dry_run_key:
        key_path = work / "throwaway.pem"
        key_path.write_bytes(S.generate_private_key_pem())
        kid = key_kid(key_path)
        print(f"Dry run: signing with a throwaway key {kid}")
    else:
        key_path = args.key
        kid = key_kid(key_path)
        expected = (ROOT / "RELEASE_KID").read_text().strip()
        if kid != expected:
            sys.exit(f"The release key's kid is {kid}, but RELEASE_KID says {expected}: wrong secret?")

    files = args.out / "v1" / "files"
    shutil.rmtree(args.out, ignore_errors=True)
    files.mkdir(parents=True)
    built: dict[tuple[str, str], str] = {}

    def add(path: Path, name: str, version: str, content: str) -> None:
        if (name, version) in built:
            sys.exit(f"{name} {version} is defined twice (official and submission?)")
        built[(name, version)] = content
        shutil.copyfile(path, files / f"{name}-{version}.json")

    # 1. Official blueprints: pack and sign.
    for yaml in sorted(ROOT.glob("blueprints/*/blueprint.yaml")):
        src = yaml.parent
        packed_path = work / f"{src.name}.json"
        nuday("validate", str(src))
        nuday("pack", str(src), "-o", str(packed_path))
        name, version, content = packed_facts(packed_path)
        nuday("sign", str(packed_path), "--key", str(key_path), "--publisher", "NuDay",
              "--expect-sha256", content)
        add(packed_path, name, version, content)
        print(f"official  {name} {version}  {content}")

    # 2. Merged partner submissions: counter-sign (the merge was the review).
    for sub in sorted(ROOT.glob("submissions/**/*.json")):
        copy = work / f"sub-{sub.name}"
        shutil.copyfile(sub, copy)
        nuday("validate", str(copy))
        name, version, content = packed_facts(copy)
        nuday("counter-sign", str(copy), "--key", str(key_path), "--expect-sha256", content)
        add(copy, name, version, content)
        print(f"reviewed  {name} {version}  {content}  ({sub.relative_to(ROOT)})")

    if not built:
        sys.exit("Nothing to publish: no blueprints/ or submissions/ yet.")

    # Published versions are immutable: changed content needs a new version.
    if args.published:
        live = fetch_published(args.published)
        changed = [f"{n} {v}" for (n, v), c in built.items() if live.get((n, v)) not in (None, c)]
        if changed:
            sys.exit("Changed content under an already published version (bump metadata.version): "
                     + ", ".join(changed))

    # 3. Build, sign and verify the index.
    index_path = args.out / "v1" / "index.json"
    meta = ROOT / "catalog" / "listings.json"
    nuday("index", "build", str(files), "-o", str(index_path), "--serial", str(int(time.time())),
          "--expires-days", str(args.expires_days), "--name", "NuDay catalog", "--base-url", "files",
          "--release-kid", kid, "--listing-meta", str(meta))
    digest = I.index_sha256(I.validate_body(json.loads(index_path.read_text())["index"]))
    nuday("index", "sign", str(index_path), "--key", str(key_path), "--expect-sha256", digest)
    print(nuday("index", "verify", str(index_path), "--trust-kid", kid))
    body = json.loads(index_path.read_text())["index"]
    for listing in body["listings"]:
        for v in listing["versions"]:
            data = (index_path.parent / v["file"]).read_bytes()
            if "sha256:" + hashlib.sha256(data).hexdigest() != v["file_sha256"]:
                sys.exit(f"{v['file']} does not match the index")
    (args.out / ".nojekyll").write_text("")
    shutil.rmtree(work, ignore_errors=True)
    print(f"Built {args.out}: {len(built)} file(s), serial {body['serial']}, expires {body['expires_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
