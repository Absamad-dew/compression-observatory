"""Measured in-memory codec calls; verification and hashing stay outside timers."""

import bz2
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import lzma
from pathlib import Path
import platform
import statistics
import time
from typing import Callable
import zlib

from . import __version__
from .corpus import sha256


@dataclass(frozen=True)
class Adapter:
    name: str
    level: int
    encode: Callable[[bytes], bytes]
    decode: Callable[[bytes], bytes]


def adapter(spec: str) -> Adapter:
    try:
        name, raw_level = spec.split(":")
        level = int(raw_level)
    except (ValueError, TypeError) as exc:
        raise ValueError("codec must have the form gzip:6, zlib:6, bz2:9 or lzma:6") from exc
    ranges = {"gzip": (0, 9), "zlib": (0, 9), "bz2": (1, 9), "lzma": (0, 9)}
    if name not in ranges or not ranges[name][0] <= level <= ranges[name][1]:
        raise ValueError(f"unsupported codec or level: {spec}")
    encoders = {"gzip": lambda data: gzip.compress(data, compresslevel=level, mtime=0),
                "zlib": lambda data: zlib.compress(data, level),
                "bz2": lambda data: bz2.compress(data, compresslevel=level),
                "lzma": lambda data: lzma.compress(data, preset=level, format=lzma.FORMAT_XZ)}
    decoders = {"gzip": gzip.decompress, "zlib": zlib.decompress,
                "bz2": bz2.decompress, "lzma": lzma.decompress}
    return Adapter(name, level, encoders[name], decoders[name])


def verify(original: bytes, restored: bytes) -> str:
    if restored != original:
        raise ValueError("lossless verification failed: decoded bytes differ")
    digest = sha256(restored)
    if digest != sha256(original):
        raise ValueError("lossless verification failed: SHA256 differs")
    return digest


def summary(samples: list[int]) -> dict:
    average = statistics.mean(samples)
    ordered = sorted(samples)
    # Nearest-rank p95; population CV, intentionally zero for a single observation.
    p95 = ordered[max(0, -(-95 * len(ordered) // 100) - 1)]
    return {"median_ns": statistics.median(samples), "p95_ns": p95,
            "cv": statistics.pstdev(samples) / average if average else 0.0}


def measure(data: bytes, codec: Adapter, warmups: int, repeats: int) -> dict:
    samples, reference = [], None
    for index in range(warmups + repeats):
        start = time.perf_counter_ns()
        encoded = codec.encode(data)
        encode_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        restored = codec.decode(encoded)
        decode_ns = time.perf_counter_ns() - start
        digest = verify(data, restored)
        output_digest = sha256(encoded)
        current = (len(encoded), output_digest)
        if reference is not None and current != reference:
            raise ValueError("codec produced nondeterministic compressed bytes")
        reference = current
        if index >= warmups:
            samples.append({"repeat": index - warmups, "encode_ns": encode_ns, "decode_ns": decode_ns})
    return {"input_bytes": len(data), "output_bytes": reference[0],
            "ratio": reference[0] / len(data) if data else None,
            "input_sha256": sha256(data), "output_sha256": reference[1], "decoded_sha256": digest,
            "verified": True, "samples": samples,
            "encode": summary([sample["encode_ns"] for sample in samples]),
            "decode": summary([sample["decode_ns"] for sample in samples])}


def aggregate(files: list[dict], repeats: int) -> dict:
    input_bytes = sum(item["input_bytes"] for item in files)
    output_bytes = sum(item["output_bytes"] for item in files)
    samples = [{"repeat": repeat,
                "encode_ns": sum(item["samples"][repeat]["encode_ns"] for item in files),
                "decode_ns": sum(item["samples"][repeat]["decode_ns"] for item in files)}
               for repeat in range(repeats)]
    return {"input_bytes": input_bytes, "output_bytes": output_bytes,
            "ratio": output_bytes / input_bytes if input_bytes else None,
            "verified": all(item["verified"] for item in files), "samples": samples,
            "encode": summary([item["encode_ns"] for item in samples]),
            "decode": summary([item["decode_ns"] for item in samples])}


def mark_pareto(results: list[dict]) -> None:
    for result in results:
        point = result["aggregate"]
        for axis in ("encode", "decode"):
            dominated = any(
                other["aggregate"]["output_bytes"] <= point["output_bytes"]
                and other["aggregate"][axis]["median_ns"] <= point[axis]["median_ns"]
                and (other["aggregate"]["output_bytes"] < point["output_bytes"]
                     or other["aggregate"][axis]["median_ns"] < point[axis]["median_ns"])
                for other in results if other is not result)
            point[f"pareto_size_{axis}"] = not dominated


def source_fingerprints() -> list[dict]:
    return [{"path": f"src/compression_observatory/{path.name}", "sha256": sha256(path.read_bytes())}
            for path in sorted(Path(__file__).parent.glob("*.py"))]


def run(files: list[tuple[str, bytes]], provenance: dict, specs: list[str], *, warmups: int = 1,
        repeats: int = 5, source_revision: str | None = None) -> dict:
    if not 0 <= warmups <= 100 or not 1 <= repeats <= 100:
        raise ValueError("warmups must be 0..100 and repeats 1..100")
    if not specs or len(set(specs)) != len(specs):
        raise ValueError("provide at least one codec with no duplicate specifications")
    if not files:
        raise ValueError("corpus must contain at least one file")
    codecs = [adapter(spec) for spec in specs]
    results = []
    # Serial, fixed ordering: scheduling policy is recorded, not hidden.
    for spec, codec in zip(specs, codecs):
        measured = [{"path": name, **measure(data, codec, warmups, repeats)} for name, data in files]
        results.append({"codec": spec, "files": measured, "aggregate": aggregate(measured, repeats)})
    mark_pareto(results)
    return {"schema_version": 1, "tool": {"name": "compression-observatory", "version": __version__,
            "source_revision": source_revision, "source_files": source_fingerprints()},
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                            "os": platform.system(), "machine": platform.machine(),
                            "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION},
            "method": {"warmups_per_file_codec": warmups, "measured_repeats": repeats,
                       "clock": "time.perf_counter_ns", "timer_resolution_seconds": time.get_clock_info("perf_counter").resolution,
                       "timed": "in-memory encode/decode calls only; validation, hashing, file I/O excluded",
                       "ordering": "serial codec-major, file-major, warmups then repetitions",
                       "aggregation": "sum bytes; median of per-repeat sums of file times",
                       "framing": "one independently compressed stream per file; includes stream headers",
                       "gzip_mtime": 0, "lzma_format": "XZ", "memory_measured": False},
            "corpus": {**provenance, "file_count": len(files), "input_bytes": sum(len(data) for _, data in files)},
            "results": results}
