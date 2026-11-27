import base64
import json
from pathlib import Path

import pytest
from Cryptodome.Signature import eddsa

from ritmelli.update.keys import KEYS
from ritmelli.update.verify import Refused, verify

FIXTURES = Path(__file__).parent / "fixtures"
# a fixed test seed, public on purpose: only a hook with its public key trusts it
SEED = eddsa.import_private_key(bytes(range(32)))
SEED_PUBLIC = base64.b64encode(SEED.public_key().export_key(format="raw")).decode()


def sign(data: bytes, number: object = 1) -> bytes:
    signature = base64.b64encode(eddsa.new(SEED, "rfc8032").sign(data)).decode()
    return json.dumps({"chave": number, "assinatura": signature}).encode()


def test_the_v0_7_0_signature_is_key_1() -> None:
    data = (FIXTURES / "v0.7.0" / "manifest.json").read_bytes()
    signature = (FIXTURES / "v0.7.0" / "manifest.json.sig").read_bytes()
    verify(data, signature, KEYS)


def test_a_key_number_in_text_names_no_key() -> None:
    keys = {2: SEED_PUBLIC}
    verify(b"{}", sign(b"{}", 2), keys)
    with pytest.raises(Refused):
        verify(b"{}", sign(b"{}", "2"), keys)
