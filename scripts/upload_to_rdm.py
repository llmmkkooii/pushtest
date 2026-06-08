"""Upload local files to a Kyoto University RDM Drive folder over WebDAV.

RDM Drive is a Nextcloud instance at https://drive.rdm.kyoto-u.ac.jp/.
Authentication is via Nextcloud App Password (set in .env, NOT the SPS-ID password).

Usage:
    # Upload a single file
    python upload_to_rdm.py --src /tmp/file.pptx \\
        --dest "/rd10154_救急部/ポリクリ症例発表/2026年度/ポリクリ16班/file.pptx"

    # Upload every file from a local directory into a remote folder
    python upload_to_rdm.py --src /tmp/rdm-inbox/Week16/ \\
        --dest-folder "/rd10154_救急部/ポリクリ症例発表/2026年度/ポリクリ16班/"

    # Dry run — print what would happen, do nothing
    python upload_to_rdm.py --src ... --dest ... --dry-run

Required env vars (read from .env in the repo root if present):
    RDM_USER          - Nextcloud username (likely the registered email)
    RDM_APP_PASSWORD  - App Password generated in drive.rdm.kyoto-u.ac.jp settings

Exit codes:
    0  success (all files uploaded or skipped as idempotent)
    1  upload error (one or more PUTs failed)
    2  configuration error (missing env vars, bad args)
    3  authentication failure (401)
    4  quota exceeded (507)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

WEBDAV_BASE = "https://drive.rdm.kyoto-u.ac.jp/remote.php/dav/files"
PPTX_MAGIC = b"PK\x03\x04"  # Office Open XML files are zip-archived


@dataclass(frozen=True)
class RdmConfig:
    user: str
    app_password: str

    def webdav_root(self) -> str:
        """User-rooted WebDAV URL (no trailing slash). Username is URL-encoded."""
        return f"{WEBDAV_BASE}/{urllib.parse.quote(self.user, safe='')}"


def load_env(env_path: Path | None = None) -> dict[str, str]:
    """Minimal .env loader — only KEY=VALUE lines, ignores comments/blanks."""
    env: dict[str, str] = {}
    if env_path is None:
        # search current dir and up to 2 parents
        for cand in [Path.cwd() / ".env", Path.cwd().parent / ".env",
                     Path(__file__).resolve().parent.parent / ".env"]:
            if cand.exists():
                env_path = cand
                break
    if env_path is None or not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load_config() -> RdmConfig:
    env = {**load_env(), **os.environ}  # actual env overrides .env
    user = env.get("RDM_USER", "").strip()
    pw = env.get("RDM_APP_PASSWORD", "").strip()
    if not user or not pw:
        raise SystemExit("ERROR: RDM_USER and RDM_APP_PASSWORD must be set in .env")
    return RdmConfig(user=user, app_password=pw)


def _auth_handler(cfg: RdmConfig) -> urllib.request.OpenerDirector:
    pwmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    pwmgr.add_password(None, WEBDAV_BASE, cfg.user, cfg.app_password)
    handler = urllib.request.HTTPBasicAuthHandler(pwmgr)
    return urllib.request.build_opener(handler)


def _encode_remote_path(remote_path: str) -> str:
    """URL-encode each path segment of a WebDAV path (preserves slashes)."""
    parts = [urllib.parse.quote(p, safe="") for p in remote_path.strip("/").split("/")]
    return "/" + "/".join(parts)


def _url_for(cfg: RdmConfig, remote_path: str) -> str:
    return cfg.webdav_root() + _encode_remote_path(remote_path)


def mkcol(opener: urllib.request.OpenerDirector, cfg: RdmConfig, remote_dir: str,
          dry_run: bool = False) -> None:
    """Create remote directory (idempotent). Walks up to create missing ancestors."""
    parts = remote_dir.strip("/").split("/")
    cumulative = ""
    for part in parts:
        cumulative = f"{cumulative}/{part}"
        url = _url_for(cfg, cumulative)
        if dry_run:
            logger.info("[dry-run] MKCOL %s", url)
            continue
        req = urllib.request.Request(url, method="MKCOL")
        try:
            opener.open(req, timeout=30)
            logger.info("MKCOL created %s", cumulative)
        except urllib.error.HTTPError as e:
            if e.code in (405, 301):
                logger.debug("MKCOL %s already exists", cumulative)
            elif e.code == 401:
                raise SystemExit("ERROR: 401 unauthorized — App Password rejected. Regenerate it.") from e
            else:
                raise


def propfind_size(opener: urllib.request.OpenerDirector, cfg: RdmConfig,
                  remote_path: str) -> int | None:
    """Return size of remote file if it exists, else None."""
    url = _url_for(cfg, remote_path)
    body = b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:getcontentlength/></d:prop></d:propfind>'
    req = urllib.request.Request(url, data=body, method="PROPFIND")
    req.add_header("Depth", "0")
    req.add_header("Content-Type", "application/xml; charset=utf-8")
    try:
        with opener.open(req, timeout=30) as resp:
            tree = ET.fromstring(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    for el in tree.iter("{DAV:}getcontentlength"):
        if el.text and el.text.isdigit():
            return int(el.text)
    return None


def put_file(opener: urllib.request.OpenerDirector, cfg: RdmConfig,
             local_path: Path, remote_path: str, dry_run: bool = False) -> str:
    """Upload local_path to remote_path. Returns 'uploaded' | 'skipped' | 'failed:<code>'."""
    if not local_path.exists():
        return f"failed:src-missing"
    size = local_path.stat().st_size
    if size == 0:
        return "failed:empty-file"

    # PPTX magic-byte sanity check
    with open(local_path, "rb") as f:
        head = f.read(4)
    if head != PPTX_MAGIC:
        logger.warning("%s: not a zip/pptx (magic bytes %r)", local_path.name, head)

    url = _url_for(cfg, remote_path)
    if dry_run:
        logger.info("[dry-run] PUT %s (%d bytes) → %s", local_path.name, size, url)
        return "uploaded"

    # Idempotency: skip if remote already has identical-size file
    existing = propfind_size(opener, cfg, remote_path)
    if existing == size:
        logger.info("%s: identical size on RDM, skipping", local_path.name)
        return "skipped"

    with open(local_path, "rb") as f:
        req = urllib.request.Request(url, data=f.read(), method="PUT")
    req.add_header("Content-Type", "application/octet-stream")
    try:
        with opener.open(req, timeout=300) as resp:
            logger.info("PUT %s → %d (%s)", local_path.name, resp.status, resp.reason)
            return "uploaded"
    except urllib.error.HTTPError as e:
        logger.error("PUT %s failed: %d %s", local_path.name, e.code, e.reason)
        if e.code == 401:
            raise SystemExit("ERROR: 401 unauthorized — App Password rejected. Regenerate it.") from e
        if e.code == 507:
            raise SystemExit("ERROR: 507 insufficient storage — RDM quota exceeded.") from e
        return f"failed:{e.code}"


def iter_local_files(src: Path) -> Iterable[Path]:
    if src.is_file():
        yield src
    elif src.is_dir():
        for p in sorted(src.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                yield p


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, required=True, help="Local file or directory")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dest", type=str, help="Full remote file path (single-file mode)")
    grp.add_argument("--dest-folder", type=str, help="Remote folder; filenames preserved (dir mode)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    cfg = load_config()
    opener = _auth_handler(cfg)

    if args.dest:
        files = list(iter_local_files(args.src))
        if len(files) != 1:
            print(f"ERROR: --dest expects a single file, got {len(files)}", file=sys.stderr)
            return 2
        dest_dir = "/".join(args.dest.strip("/").split("/")[:-1])
        mkcol(opener, cfg, dest_dir, dry_run=args.dry_run)
        result = put_file(opener, cfg, files[0], args.dest, dry_run=args.dry_run)
        print(f"{result}\t{files[0].name}")
        return 0 if result in ("uploaded", "skipped") else 1

    # dir mode
    dest_folder = args.dest_folder.strip("/")
    mkcol(opener, cfg, dest_folder, dry_run=args.dry_run)
    any_failed = False
    for local in iter_local_files(args.src):
        remote = f"/{dest_folder}/{local.name}"
        result = put_file(opener, cfg, local, remote, dry_run=args.dry_run)
        print(f"{result}\t{local.name}")
        if result.startswith("failed"):
            any_failed = True
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
