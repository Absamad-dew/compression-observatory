"""Deterministic public fixtures and bounded, non-link-following input reads."""

import hashlib
import json
import os
from pathlib import Path
import random
import stat

MANIFEST = "corpus-manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_link(info: os.stat_result) -> bool:
    # Windows junctions/reparse points must also be excluded.
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def generate(destination: Path, *, seed: int = 1729, records: int = 2000) -> dict:
    if not 1 <= records <= 100_000:
        raise ValueError("records must be between 1 and 100000")
    if destination.resolve() != destination.absolute():
        raise ValueError("generation destination must not traverse links")
    if destination.exists() and (is_link(destination.lstat()) or not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("generation requires a new or empty directory")
    destination.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    rows, logs, prose = [], [], []
    words = ["public", "river", "measure", "sample", "cloud", "garden", "repeat", "signal"]
    for index in range(records):
        rows.append(json.dumps({"id": index, "region": rng.choice(["north", "south", "east", "west"]),
                                "active": index % 3 != 0, "value": rng.randrange(100_000),
                                "tags": rng.sample(words, 3)}, sort_keys=True, separators=(",", ":")))
        logs.append(f"event={index:06d} service=demo status={rng.choice([200, 200, 200, 404, 503])} latency_us={rng.randrange(50000)}")
        prose.append(" ".join(rng.choices(words, k=24)) + ".")
    fixtures = {"events.jsonl": ("\n".join(rows) + "\n").encode(),
                "service.log": ("\n".join(logs) + "\n").encode(),
                "prose.txt": ("\n".join(prose) + "\n").encode(),
                "unicode.txt": ("Открытые данные · 公開データ · public data\n" * records).encode(),
                "noise.bin": rng.randbytes(records * 64),
                "repeated.txt": b"A public synthetic repeated record.\n" * records,
                "empty.bin": b""}
    manifest = {"kind": "public-synthetic", "generator": "compression-observatory/corpus-v1",
                "seed": seed, "records": records,
                "files": [{"path": name, "bytes": len(data), "sha256": sha256(data)}
                          for name, data in sorted(fixtures.items())]}
    for name, data in fixtures.items():
        (destination / name).write_bytes(data)
    (destination / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def read_directory(root: Path, *, max_files: int = 1000, max_file_bytes: int = 16_777_216,
                   max_total_bytes: int = 67_108_864) -> tuple[list[tuple[str, bytes]], dict]:
    if min(max_files, max_file_bytes, max_total_bytes) < 1:
        raise ValueError("input bounds must be positive")
    if is_link(root.lstat()) or not root.is_dir() or root.resolve() != root.absolute():
        raise ValueError("input must be a directory without link traversal")
    base = root.resolve()
    result, total, manifest_data = [], 0, None

    def visit(directory: Path) -> None:
        nonlocal total, manifest_data
        with os.scandir(directory) as entries:
            children = sorted(entries, key=lambda entry: entry.name)
        for entry in children:
            path = Path(entry.path)
            # A fresh lstat is intentional: Windows DirEntry.stat may cache zero
            # file IDs, which cannot be compared to an opened handle's fstat.
            info = path.lstat()
            if is_link(info):
                raise ValueError(f"links/reparse points are not allowed: {path.relative_to(base)}")
            if stat.S_ISDIR(info.st_mode):
                visit(path)
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("only regular files are supported")
            # Resolve immediately before opening; O_NOFOLLOW additionally protects Unix leaf races.
            if not path.resolve().is_relative_to(base):
                raise ValueError("input escaped its directory")
            if info.st_size > max_file_bytes:
                raise ValueError("input exceeds max-file-bytes")
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags), "rb") as handle:
                opened = os.fstat(handle.fileno())
                if is_link(opened) or not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError("input changed while opening")
                data = handle.read(min(max_file_bytes, max_total_bytes - total) + 1)
            if len(data) > max_file_bytes or total + len(data) > max_total_bytes:
                raise ValueError("input exceeds byte limits")
            total += len(data)
            name = path.relative_to(base).as_posix()
            if name == MANIFEST:
                manifest_data = data
            else:
                result.append((name, data))
                if len(result) > max_files:
                    raise ValueError("input exceeds max-files")

    visit(base)
    if not result:
        raise ValueError("input directory contains no corpus files")
    provenance = {"kind": "user-directory", "manifest_sha256": None}
    if manifest_data is not None:
        manifest = json.loads(manifest_data)
        actual = [{"path": name, "bytes": len(data), "sha256": sha256(data)} for name, data in result]
        if manifest.get("files") != actual:
            raise ValueError("corpus manifest does not match input bytes")
        # A matching manifest is an assertion, not proof of origin.
        provenance = {"kind": "manifest-verified", "declared_kind": manifest.get("kind"),
                      "manifest_sha256": sha256(manifest_data), "manifest": manifest}
    return result, provenance
