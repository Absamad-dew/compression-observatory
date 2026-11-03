# Measured example provenance

This example was actually regenerated on 2026-11-03 using CPython 3.13.15 on Windows/AMD64 after fixing Windows path-alias handling. It uses only the public synthetic generator in this repository: seed `1729`, `2000` records, seven files, 951,109 input bytes. No private R&D inputs or algorithms were used. The complete manifest is embedded in `run.json` and copied to `corpus-manifest.json`.

The earlier measurement and its original source remain available unchanged in [public commit 7ff92aa2ad1eb4b72be95dbb76f32e72ef904197](https://github.com/Absamad-dew/compression-observatory/tree/7ff92aa2ad1eb4b72be95dbb76f32e72ef904197/examples). The current numbers come from a new real run; the earlier fingerprints were not edited to pretend that an old run measured the fix.

## Current run

The package was rebuilt and installed in its local virtual environment using `python -m pip install .`. Execution used installed CoreBroker 0.6.2, stable project `github-portfolio`, `--auto --json`, nonexclusive, no power-plan changes. Status/recommend were inspected first. The L3 reservation stayed enabled. No claim is made that unmanaged Windows activity was excluded.

Portable equivalent of the actual commands (use your installed CoreBroker path):

```sh
corebroker run --project github-portfolio --auto --json -- compression-observatory generate results/portability-corpus --seed 1729 --records 2000
corebroker bench --project github-portfolio --auto --json --warmups 1 --runs 3 -- compression-observatory bench results/portability-corpus --codecs gzip:1,gzip:6,zlib:6,bz2:9,lzma:6 --warmups 1 --repeats 5 --json examples/run.json --html examples/report.html
python tools/refresh_preview.py
python tools/check_example.py
```

The actual child executable was `.venv\Scripts\compression-observatory.exe`; arguments and outer metrics are preserved in [corebroker-run.json](corebroker-run.json). CoreBroker ran one outer warmup plus three complete child runs. `run.json` / `report.html` retain the **last** child run; each child independently performs one per-file/codec warmup plus five measured repetitions. The three outer wall durations (which include Python startup, reports, verification and hashing) were 1854.5896, 1838.4359 and 2040.9761 ms; median 1854.5896 ms, p95 2040.9761 ms, CV 4.8086%. They are not the codec-call times and are not a performance comparison with the historical run.

Benchmark lease `411b7b7b-397e-4a12-beee-53a91c394f49`: physical core identifiers `[16,18,20,22,24,26,28,30]`, logical CPUs `16..31`, L3 identifier `16`, nonexclusive, exit `0`. Identifiers follow CoreBroker's topology numbering: eight physical cores with SMT. CoreBroker is a private external coordination tool; its implementation is neither included nor required to use this public benchmark.

`run.json` records the exact current Python source-file SHA256 fingerprints, interpreter/runtime metadata, corpus hashes, individual repetitions, byte-weighted ratios and Pareto flags. The source revision field is null because the fix was measured from an uncommitted working tree based on `7ff92aa`; the recorded fingerprints identify the measured Python files. `tools/check_example.py` continues to compare those fingerprints to the current source, without a historical-source bypass. `report-preview.svg` is generated from the new measurements.

## Path portability regression and validation

The [initial hosted Windows/Python 3.11 job](https://github.com/Absamad-dew/compression-observatory/actions/runs/41636767367) failed on ordinary temporary directories. The original guard treated `path.resolve() != path.absolute()` as proof of a symlink. Windows `resolve()` also expands legitimate 8.3 short-name aliases; case normalization alone cannot equate those different spellings.

The same defect was reproduced locally with `GetShortPathNameW` on a newly created temporary directory: the published package rejected the alias even though it was not a link. The fix checks `lstat` metadata on each existing path component before resolving the root. Symlinks and Windows reparse points are still rejected, including ancestors, and `..` traversal is rejected before normalization.

The regression tests exercise real Windows short-path generate/read calls (including the Windows/Python 3.11 CI matrix), a spelling-only mismatch, ancestor reparse metadata and parent traversal. They add no test skips. Locally, the final installed-package suite ran **15 tests: 14 passed and one pre-existing symlink-creation test skipped** because this Windows session does not grant link creation. The new short-alias and boundary regressions passed. Test lease `6d82b6c3-eef2-43ca-907c-cfffa2cf6298`: physical identifiers `[0,2,4,6,8,10,12,14]`, logical CPUs `0..15`, L3 `0`, nonexclusive, exit `0`. Local Python 3.11 is not installed; a passing hosted rerun of the fix has not been observed when recording this artifact.

The initial local implementation also encountered Windows cached `DirEntry.stat` file IDs and a failed `--no-build-isolation` reinstall without setuptools; both were resolved before the first published example. The documented normal `pip install .` installation succeeds. These historical failures are not presented as passing checks.

The corpus is intentionally synthetic. Measurements do not establish general codec superiority, private research performance, memory usage, deployment experience or a production claim.
