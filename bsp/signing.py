# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Signed approvals.

The owner's private Ed25519 key lives only on the owner's machine
(``~/.motorpool/signing_key``). Its public key is listed in
``data/trusted_keys.yaml`` in the repository. An approval is *verified* when
its signature checks out against the trusted key for the approver's name, so
nobody else can produce a verified "Approved-Launchpad", even by editing files.

Owner setup (once, on the owner's machine):
    python -m bsp.signing init --name Launchpad
    python -m bsp.signing sign-existing        # sign earlier, unsigned approvals
then commit data/trusted_keys.yaml and data/approvals.yaml.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PrivateKey,
                                                               Ed25519PublicKey)

ROOT = Path(__file__).resolve().parent.parent
TRUSTED = ROOT / "data" / "trusted_keys.yaml"
HOME = Path.home() / ".motorpool"
KEY_FILE = HOME / "signing_key"


def canonical(entry: dict) -> bytes:
    """The signed bytes: everything in the approval except the signature."""
    body = {k: v for k, v in entry.items() if k not in ("sig", "verified")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()


def load_private(path: Path = KEY_FILE) -> Ed25519PrivateKey | None:
    if not path.exists():
        return None
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def public_b64(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw,
                                        serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def trusted_keys(path: Path = TRUSTED) -> dict[str, str]:
    if not path.exists():
        return {}
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("keys", {}) or {}


def sign(entry: dict, key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.sign(canonical(entry))).decode()


def verify(entry: dict, keys: dict[str, str] | None = None) -> bool:
    keys = trusted_keys() if keys is None else keys
    pub, sig = keys.get(entry.get("by", "")), entry.get("sig")
    if not pub or not sig:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(pub)).verify(
            base64.b64decode(sig), canonical(entry))
        return True
    except (InvalidSignature, ValueError):
        return False


def owner_name(key: Ed25519PrivateKey | None = None) -> str | None:
    """The trusted name this machine's key signs for, if any."""
    key = key or load_private()
    if key is None:
        return None
    mine = public_b64(key)
    for name, pub in trusted_keys().items():
        if pub == mine:
            return name
    return None


def init(name: str) -> str:
    HOME.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        key = load_private()
    else:
        key = Ed25519PrivateKey.generate()
        KEY_FILE.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        try:
            KEY_FILE.chmod(0o600)
        except OSError:
            pass
    data = {"keys": trusted_keys()}
    data["keys"][name] = public_b64(key)
    TRUSTED.write_text("# Public keys whose signatures make an approval verified.\n"
                       "# The matching private keys never leave their owners' machines.\n"
                       + yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return public_b64(key)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Signing keys for approvals")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create this machine's key and trust it under NAME")
    p.add_argument("--name", required=True)
    sub.add_parser("sign-existing", help="sign unsigned approvals made under the owner's name")
    sub.add_parser("whoami", help="show which trusted name this machine signs as")
    a = ap.parse_args(argv)
    if a.cmd == "init":
        print("Public key:", init(a.name))
        print(f"Trusted as {a.name} in {TRUSTED}. Private key: {KEY_FILE} (keep it private).")
    elif a.cmd == "whoami":
        print(owner_name() or "No trusted signing key on this machine.")
    elif a.cmd == "sign-existing":
        from . import approvals
        n = approvals.sign_existing()
        print(f"Signed {n} approval(s).")


if __name__ == "__main__":
    main()
