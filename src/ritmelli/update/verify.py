"""The signature of a manifest, as v0.7.0 checks it. The .sig is
{"chave": <number>, "assinatura": <base64>}: an Ed25519 signature of the exact
manifest bytes, by the key with that number."""

import base64
import json
from collections.abc import Mapping

from Cryptodome.Signature import eddsa


class Refused(ValueError):
    """The manifest or the file fails the check."""


def verify(manifest: bytes, signature: bytes, keys: Mapping[int, str]) -> None:
    """Refused unless one of keys signed manifest. The number must be an integer:
    "2" names no key."""
    try:
        sig = json.loads(signature)
        public = eddsa.import_public_key(
            base64.b64decode(keys[sig["chave"]], validate=True)
        )
        eddsa.new(public, "rfc8032").verify(
            manifest, base64.b64decode(sig["assinatura"], validate=True)
        )
    except (KeyError, TypeError, ValueError) as error:
        raise Refused("the manifest signature doesn't match") from error
