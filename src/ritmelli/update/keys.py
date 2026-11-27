"""Where the update finds the manifest, and the keys it trusts. The signature is at
the same address with ".sig" at the end.

These are the keys of v0.7.0. Key 2 signs the new line; key 1 signed v0.7.0 and is
the reserve. The hook's Chave value replaces both, as key 1."""

MANIFEST_URL = "https://github.com/ritmelli/ritmelli-releases/releases/latest/download/manifest.json"
# number -> Ed25519 public key (the 32 bytes in base64); the .sig names the number
KEYS = {
    1: "Bnvi5qyGzrl2bPDgG9UUCDHjhcTCU3lr9SHMKbkjLts=",
    2: "hwKHawdmYamR9AjaI5uYxKXTDHKiyVUIoh+9afyBYWM=",
}
