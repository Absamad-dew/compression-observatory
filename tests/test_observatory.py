import json
import os
from pathlib import Path
import statistics
import tempfile
import unittest
from unittest.mock import patch

from compression_observatory.benchmark import Adapter, adapter, aggregate, mark_pareto, measure, run, summary
from compression_observatory.cli import main
from compression_observatory.corpus import generate, read_directory, reject_link_components, sha256
from compression_observatory.report import render


class RoundTripTests(unittest.TestCase):
    def test_all_codecs_empty_unicode_and_noise(self):
        payloads = [b"", "Открытые данные ∑\n".encode() * 20, bytes(range(256)) * 8]
        for spec in ["gzip:0", "gzip:9", "zlib:0", "zlib:9", "bz2:1", "bz2:9", "lzma:0"]:
            for payload in payloads:
                with self.subTest(spec=spec, size=len(payload)):
                    item = measure(payload, adapter(spec), 1, 2)
                    self.assertEqual(item["decoded_sha256"], sha256(payload))
                    self.assertEqual(len(item["samples"]), 2)
                    self.assertEqual(item["ratio"], item["output_bytes"] / len(payload) if payload else None)

    def test_corruption_failure_and_nondeterminism_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "decoded bytes differ"):
            measure(b"expected", Adapter("broken", 1, bytes, lambda _: b"corrupt"), 0, 1)
        def broken(_):
            raise RuntimeError("adapter failed")
        with self.assertRaisesRegex(RuntimeError, "adapter failed"):
            measure(b"expected", Adapter("broken", 1, broken, bytes), 0, 1)
        counter = iter([b"a", b"b"])
        with self.assertRaisesRegex(ValueError, "nondeterministic"):
            measure(b"original", Adapter("unstable", 1, lambda _: next(counter), lambda _: b"original"), 1, 1)

    def test_timers_exclude_validation_and_warmups(self):
        ticks = iter([0, 10, 20, 50, 100, 120, 130, 170, 200, 230, 240, 290])
        with patch("compression_observatory.benchmark.time.perf_counter_ns", side_effect=lambda: next(ticks)):
            result = measure(b"x", Adapter("identity", 0, bytes, bytes), 1, 2)
        self.assertEqual(result["samples"], [{"repeat": 0, "encode_ns": 20, "decode_ns": 40},
                                             {"repeat": 1, "encode_ns": 30, "decode_ns": 50}])
        self.assertEqual(result["encode"]["median_ns"], 25)
        self.assertEqual(summary([1, 2, 100])["p95_ns"], 100)

    def test_weighted_aggregation_and_median_of_sums(self):
        files = [dict(input_bytes=1, output_bytes=10, verified=True, samples=[dict(encode_ns=x, decode_ns=x) for x in [1, 100, 2]]),
                 dict(input_bytes=99, output_bytes=9, verified=True, samples=[dict(encode_ns=x, decode_ns=x) for x in [100, 1, 2]])]
        total = aggregate(files, 3)
        self.assertEqual(total["ratio"], 19 / 100)
        self.assertEqual(total["encode"]["median_ns"], 101)
        self.assertNotEqual(total["encode"]["median_ns"], sum(statistics.median([s["encode_ns"] for s in f["samples"]]) for f in files))

    def test_pareto_tradeoffs_ties_and_dominance(self):
        results = [{"aggregate": {"output_bytes": size, "encode": {"median_ns": enc}, "decode": {"median_ns": dec}}}
                   for size, enc, dec in [(10, 10, 10), (20, 20, 5), (5, 30, 30), (10, 10, 10)]]
        mark_pareto(results)
        self.assertEqual([r["aggregate"]["pareto_size_encode"] for r in results], [True, False, True, True])
        self.assertEqual([r["aggregate"]["pareto_size_decode"] for r in results], [True, True, True, True])


class DirectoryTests(unittest.TestCase):
    def test_resolved_spelling_is_not_used_to_detect_links(self):
        # A resolve/absolute spelling mismatch can be a Windows 8.3 alias,
        # not a symlink. The metadata check must not reject that mismatch.
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "corpus"
            resolve = Path.resolve
            def canonical_spelling(path, *args, **kwargs):
                if path == destination:
                    return path.parent / "different-canonical-spelling"
                return resolve(path, *args, **kwargs)
            with patch.object(Path, "resolve", canonical_spelling):
                generate(destination, records=2)
            self.assertEqual(len(read_directory(destination)[0]), 7)

    def test_windows_temp_short_alias_generate_and_read(self):
        # Runs on Windows 3.11 in CI, where TEMP can contain RUNNER~1.
        # Other platforms still exercise the same temporary-directory workflow.
        with tempfile.TemporaryDirectory(prefix="compression-observatory-long-name-") as temp:
            alias = temp
            if os.name == "nt":
                import ctypes
                buffer = ctypes.create_unicode_buffer(32768)
                length = ctypes.windll.kernel32.GetShortPathNameW(temp, buffer, len(buffer))
                self.assertGreater(length, 0)
                self.assertLess(length, len(buffer))
                alias = buffer.value
            destination = Path(alias) / "corpus"
            generate(destination, records=2)
            self.assertEqual(len(read_directory(destination)[0]), 7)

    def test_ancestor_reparse_metadata_and_parent_traversal_are_rejected(self):
        from types import SimpleNamespace
        import stat
        with tempfile.TemporaryDirectory() as temp:
            ancestor = Path(temp)
            original = Path.lstat
            def reparse_metadata(path):
                if path == ancestor:
                    return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return original(path)
            with patch.object(Path, "lstat", reparse_metadata):
                with self.assertRaisesRegex(ValueError, "links/reparse"):
                    generate(ancestor / "corpus", records=2)
                with self.assertRaisesRegex(ValueError, "links/reparse"):
                    read_directory(ancestor / "corpus")
            with self.assertRaisesRegex(ValueError, "parent traversal"):
                reject_link_components(ancestor / "missing" / ".." / "corpus", allow_missing=True)
            self.assertFalse((ancestor / "corpus").exists())

    def test_deterministic_manifest_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "a", Path(temp) / "b"
            self.assertEqual(generate(a, seed=42, records=8), generate(b, seed=42, records=8))
            self.assertNotIn(b"\r\n", (a / "corpus-manifest.json").read_bytes())
            inputs, provenance = read_directory(a)
            self.assertEqual(provenance["kind"], "manifest-verified")
            self.assertEqual(provenance["manifest"]["seed"], 42)
            self.assertEqual(len(inputs), 7)
            (a / "prose.txt").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "manifest"):
                read_directory(a)

    def test_directory_and_file_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").write_bytes(b"1234")
            (root / "nested").mkdir()
            (root / "nested" / "b").write_bytes(b"5678")
            for limits in [dict(max_files=1), dict(max_file_bytes=3), dict(max_total_bytes=7)]:
                with self.subTest(limits=limits), self.assertRaises(ValueError):
                    read_directory(root, **limits)
            self.assertEqual([name for name, _ in read_directory(root)[0]], ["a", "nested/b"])

    def test_symlink_is_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "input"
            root.mkdir()
            outside = Path(temp) / "outside"
            outside.write_bytes(b"never read")
            try:
                (root / "link").symlink_to(outside)
            except OSError:
                self.skipTest("symlinks require Windows developer mode or appropriate privileges")
            with self.assertRaisesRegex(ValueError, "links/reparse"):
                read_directory(root)

    def test_windows_reparse_points_are_recognized(self):
        from compression_observatory.corpus import is_link
        from types import SimpleNamespace
        import stat
        self.assertTrue(is_link(SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)))


class IntegrationTests(unittest.TestCase):
    def test_provenance_report_escaping_and_portability(self):
        result = run([("<script>.txt", b"public text" * 30)], {"kind": "user-directory"}, ["gzip:6", "zlib:6"], warmups=0, repeats=2)
        encoded = json.dumps(result, allow_nan=False)
        self.assertNotIn(str(Path.cwd()), encoded)
        self.assertNotIn("hostname", result["environment"])
        self.assertEqual(result["tool"]["source_files"][0]["path"].split("/")[0], "src")
        page = render(result)
        self.assertIn("&lt;script&gt;.txt", page)
        self.assertNotIn("<script>", page)
        self.assertNotIn("https://", page)
        self.assertIn("Content-Security-Policy", page)

    def test_independent_cli_generate_bench_and_rerender(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            corpus, output, html = root / "input", root / "result.json", root / "report.html"
            self.assertEqual(main(["generate", str(corpus), "--records", "3"]), 0)
            self.assertEqual(main(["bench", str(corpus), "--codecs", "gzip:6,zlib:6", "--warmups", "0", "--repeats", "2", "--json", str(output), "--html", str(html)]), 0)
            original = html.read_bytes()
            self.assertEqual(main(["report", str(output), "--html", str(html)]), 0)
            self.assertEqual(original, html.read_bytes())
            self.assertEqual(main(["bench", str(corpus), "--json", str(corpus / "unsafe.json"), "--html", str(html)]), 2)
            self.assertFalse((corpus / "unsafe.json").exists())

    def test_invalid_configuration_has_no_successful_result(self):
        for spec in ["pickle:1", "lzma:10", "bz2:0", "gzip", "gzip:6:7"]:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                adapter(spec)
        for kwargs in [dict(warmups=-1), dict(repeats=0)]:
            with self.assertRaises(ValueError):
                run([("x", b"x")], {}, ["gzip:6"], **kwargs)
        with self.assertRaises(ValueError):
            run([("x", b"x")], {}, ["gzip:6", "gzip:6"])


if __name__ == "__main__":
    unittest.main()
