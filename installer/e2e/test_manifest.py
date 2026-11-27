"""The test manifests of the crossing, from the build-info.json of each test build. They
have the format of a published manifest, for app "ritmelli", without the partial setup
and the file list, and point to the setup next to them on the local server. One call
signs them all with a key made here, as "chave": 1, and prints its public key: only a
PC whose hook holds it in Chave trusts them. The private key never reaches the disk.

    test_manifest.py <url> <folder> <build-info.json>...
        writes v<version>/manifest.json and its .sig in folder for each build, and the
        same for the highest version in latest/; the setup of each is expected at
        <url>/v<version>/Ritmelli-<version>-setup.exe
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

from Cryptodome.PublicKey import ECC
from Cryptodome.Signature import eddsa

from ritmelli.update.manifest import APP, FORMAT, parse_version


def manifest(info: dict[str, Any], url: str) -> dict[str, Any]:
    version = info["version"]
    setup = f"Ritmelli-{version}-setup.exe"
    artifact = info["artifacts"][setup]
    return {
        "formato": FORMAT,
        "app": APP,
        "versao": version,
        "data": time.strftime("%Y-%m-%d"),
        "instalador": {
            "url": f"{url}/v{version}/{setup}",
            "sha256": artifact["sha256"],
            "tamanho": artifact["size"],
        },
    }


def write(url: str, folder: Path, infos: list[Path]) -> str:
    """Writes the manifests and returns the public key, in base64."""
    manifests = [manifest(json.loads(p.read_bytes()), url) for p in infos]
    latest = max(manifests, key=lambda m: parse_version(m["versao"]))
    named = {f"v{m['versao']}": m for m in manifests} | {"latest": latest}
    key = ECC.generate(curve="Ed25519")
    signer = eddsa.new(key, "rfc8032")
    for name, m in named.items():
        data = (json.dumps(m, indent=1) + "\n").encode()
        signature = base64.b64encode(signer.sign(data)).decode()
        (folder / name).mkdir(parents=True, exist_ok=True)
        (folder / name / "manifest.json").write_bytes(data)
        sig = json.dumps({"chave": 1, "assinatura": signature}) + "\n"
        (folder / name / "manifest.json.sig").write_bytes(sig.encode())
    return base64.b64encode(key.public_key().export_key(format="raw")).decode()


def main(args: list[str]) -> None:
    if len(args) < 3:
        sys.exit(__doc__)
    print(write(args[0], Path(args[1]), [Path(arg) for arg in args[2:]]))


if __name__ == "__main__":
    main(sys.argv[1:])
