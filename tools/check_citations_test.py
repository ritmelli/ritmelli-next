import check_citations

NAMES = [
    "installer/ritmelli.iss",
    "src/ritmelli/machine/mic_setup.py",
    "src/ritmelli/update/client.py",
]
LENGTHS = dict(zip(NAMES, (120, 140, 210), strict=True))
SERVER = (
    "the endpoint answers `409` when the version is not ready (`server.py:2414-2420`)."
)
MIGRATION = (
    "1. `_migra_registro`, the copy of the old Vitrola registry before any microphone"
    " changes (`microfone.py:1049-1057`, called at `:1084-1085`)."
)


def wrong(body: str) -> list[str]:
    return check_citations.wrong(body, NAMES, LENGTHS.__getitem__)


def test_a_file_of_another_tree_fails_until_the_citation_names_the_tree() -> None:
    assert wrong(f"Kind: core\n\n{SERVER}\n{MIGRATION}") == [
        "line 3: server.py:2414-2420: no such file at the head",
        "line 4: microfone.py:1049-1057: no such file at the head",
    ]
    assert wrong(SERVER.replace("2420`", "2420` of `v0.7.0`")) == []
    assert wrong(MIGRATION.replace("1057`", "1057` at `8cacd23`")) == []


def test_a_line_past_the_end_of_the_file_fails() -> None:
    body = "`installer/ritmelli.iss:101-120`, `update/client.py:24`, `mic_setup.py:121-141`"
    assert wrong(body) == ["line 1: mic_setup.py:121-141: the file has 140 lines"]


def test_the_proof_and_the_review_are_not_read() -> None:
    planted = "exit 1 (`src/ritmelli/machine/planted_word.py:1`, `MIC_ACTIONS[1]`)"
    quoted = "the cut list cited a path that does not exist for `server.py:2414-2420`"
    assert wrong(f"## Proof\n\n{planted}\n\n## Review\n\n{quoted}") == []
    assert len(wrong(f"## What was cut\n\n{planted}\n{quoted}")) == 2


def test_an_address_a_repo_and_a_bare_line_are_not_citations() -> None:
    body = (
        "serves the test manifests on `127.0.0.1:8765`, as"
        " `ritmelli/ritmelli:app/server.py:2414-2420` does, called at `:1084-1085`"
    )
    assert wrong(body) == []
