# Measured example provenance

This example was actually generated on 2026-11-03 using CPython 3.13.15 on Windows/AMD64. It uses only the public synthetic generator in this repository: seed `1729`, `2000` records, seven files (including an empty file and pseudo-random bytes). No private R&D inputs or algorithms were used. The complete manifest is embedded in `run.json` and copied to `corpus-manifest.json`.

The package was built and installed in a clean local virtual environment using `python -m pip install .`. Benchmark execution used installed CoreBroker 0.6.2, stable project `github-portfolio`, `--auto --json`, nonexclusive, no power-plan changes. Status/recommend were inspected first; doctor reported AC power and 16 physical / 32 logical CPUs. CoreBroker's L3 reservation stayed enabled. No claim is made that unmanaged Windows activity was excluded.

Portable equivalent of the commands (use your installed CoreBroker path):

```sh
corebroker run --project github-portfolio --auto --json -- compression-observatory generate corpus-final --seed 1729 --records 2000
corebroker bench --project github-portfolio --auto --json --warmups 1 --runs 3 -- compression-observatory bench corpus-final --codecs gzip:1,gzip:6,zlib:6,bz2:9,lzma:6 --warmups 1 --repeats 5 --json examples/run.json --html examples/report.html
python tools/refresh_preview.py
```

The actual child executable was `.venv\Scripts\compression-observatory.exe`; all argument values and reported outer metrics are preserved in [corebroker-run.json](corebroker-run.json). CoreBroker ran one outer warmup plus three complete child runs. `run.json` / `report.html` retain the **last** child run; each child independently performs one per-file/codec warmup plus five measured repetitions. The three outer wall durations (which include Python startup, generation of reports, verification and hashing) were 1783.4352, 1804.999 and 1828.152 ms; median 1804.999 ms, p95 1828.152 ms, CV 1.0113%. They are not the codec-call times.

Outer benchmark lease `5e22eb2e-e1bf-47ff-807b-e9f5d607e800`: physical core identifiers `[16,18,20,22,24,26,28,30]`, logical CPUs `16..31`, L3 identifier `16`, nonexclusive, exit code `0`. Identifiers follow CoreBroker's topology numbering. These are eight physical cores with SMT, not sixteen physical cores. CoreBroker is a private external coordination tool; its implementation is neither included nor required to use this public benchmark.

`run.json` contains actual source-file SHA256 fingerprints, interpreter/runtime metadata, corpus hashes, individual repetitions, correct byte-weighted ratios and Pareto flags. The source revision field is null because this fresh source tree was measured before its first public commit; fingerprints identify the exact measured Python files. Do not edit measurements to match a later revision. Reproduce the corpus and rerun instead. `report-preview.svg` is generated from these saved measurements, not hand-entered benchmark values.

## Validation performed locally

* Normal package installation succeeded independently of sibling repositories.
* Final installed-package suite: `python -m unittest discover -s tests -v`, 12 tests run, 11 passed and one symlink-creation test skipped because this Windows session does not grant link creation. CoreBroker test lease `68540218-4e32-4145-b993-1ff23169cb1b`, nonexclusive, physical identifiers `[0,2,4,6]`, logical CPUs `0..7`, L3 `0`, exit `0`. The automatic allocator chose four physical cores for that run based on shared project history.
* Initial tests exposed a Windows portability defect: cached `DirEntry.stat` returned zero file IDs while `fstat` returned the actual IDs. Replacing that cached metadata with fresh `Path.lstat` fixed the identity check. The suite was reinstalled and rerun successfully.
* An attempted local reinstall with `--no-build-isolation` failed because the fresh Python 3.13 virtual environment lacked setuptools. Repeating the documented normal `pip install .` succeeded. The public quickstart does not use that unsupported local shortcut.
* A final portability audit made text output explicitly LF on all platforms, added a newline assertion and LF checkout attributes, and regenerated the measured example from the final source. `python tools/check_example.py` verifies source hashes, manifest, byte totals and timing aggregation without editing measured values.
* Linux/Windows CI is configured, but hosted runs have not been observed as part of this local run.

The corpus is intentionally synthetic. These measurements do not establish general codec superiority, private research performance, memory usage, deployment experience or a production claim.
