"""Explicit local inputs; no plugin imports, shell commands or network access."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .benchmark import run
from .corpus import generate, read_directory
from .report import render


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Byte-verified stdlib lossless compression experiments")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    corpus = commands.add_parser("generate", help="create a public deterministic mixed synthetic corpus")
    corpus.add_argument("directory", type=Path)
    corpus.add_argument("--seed", type=int, default=1729)
    corpus.add_argument("--records", type=int, default=2000)
    bench = commands.add_parser("bench", help="measure a bounded local directory")
    bench.add_argument("directory", type=Path)
    bench.add_argument("--codecs", default="gzip:1,gzip:6,zlib:6,bz2:9,lzma:6")
    bench.add_argument("--warmups", type=int, default=1)
    bench.add_argument("--repeats", type=int, default=5)
    bench.add_argument("--max-files", type=int, default=1000)
    bench.add_argument("--max-file-bytes", type=int, default=16_777_216)
    bench.add_argument("--max-total-bytes", type=int, default=67_108_864)
    bench.add_argument("--source-revision", help="optional declared source revision; source hashes are always recorded")
    bench.add_argument("--json", dest="json_path", type=Path, required=True)
    bench.add_argument("--html", dest="html_path", type=Path, required=True)
    report = commands.add_parser("report", help="render an existing measurement JSON without benchmarking")
    report.add_argument("json_path", type=Path)
    report.add_argument("--html", dest="html_path", type=Path, required=True)
    return root


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            manifest = generate(args.directory.absolute(), seed=args.seed, records=args.records)
            print(f"Generated {len(manifest['files'])} public synthetic files; seed={args.seed}, records={args.records}")
        elif args.command == "bench":
            source = args.directory.absolute()
            if args.json_path.resolve() == args.html_path.resolve():
                raise ValueError("JSON and HTML outputs must be different files")
            if any(path.resolve().is_relative_to(source.resolve()) for path in (args.json_path, args.html_path)):
                raise ValueError("report outputs must be outside the input directory")
            files, provenance = read_directory(source, max_files=args.max_files,
                                                max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes)
            report = run(files, provenance, [item.strip() for item in args.codecs.split(",")],
                         warmups=args.warmups, repeats=args.repeats, source_revision=args.source_revision)
            html = render(report)
            write(args.json_path, json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
            write(args.html_path, html)
            print(f"Verified {len(files)} files across {len(report['results'])} codec configurations; wrote JSON and HTML")
        else:
            if args.json_path.resolve() == args.html_path.resolve():
                raise ValueError("HTML output must not overwrite measurement JSON")
            report = json.loads(args.json_path.read_text(encoding="utf-8"))
            if report.get("schema_version") != 1:
                raise ValueError("unsupported report schema")
            write(args.html_path, render(report))
            print("Rendered HTML report")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, EOFError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
