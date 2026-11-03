"""Self-contained escaped HTML and inline SVG; no scripts or remote resources."""

from html import escape
import json


def render(report: dict) -> str:
    rows = report["results"]
    esc = lambda value: escape(str(value), quote=True)
    max_size = max(item["aggregate"]["output_bytes"] for item in rows) or 1
    max_time = max(item["aggregate"]["encode"]["median_ns"] for item in rows) or 1
    colors = ["#007f79", "#c15322", "#6950ab", "#3374af", "#9a3d70", "#7d7224"]
    dots, table, details = [], [], []
    for index, item in enumerate(rows):
        point = item["aggregate"]
        x = 80 + 680 * point["output_bytes"] / max_size
        y = 325 - 255 * point["encode"]["median_ns"] / max_time
        color = colors[index % len(colors)]
        label = esc(item["codec"])
        dots.append(f'<g><title>{label}: {point["output_bytes"]:,} bytes, {point["encode"]["median_ns"]/1e6:.3f} ms</title><circle cx="{x:.2f}" cy="{y:.2f}" r="10" fill="{color}" stroke="white" stroke-width="2"/><text x="{x:.2f}" y="{y+4:.2f}" text-anchor="middle" style="fill:white;font-size:11px">{index+1}</text></g>')
        ratio = f'{point["ratio"]:.4f}' if point["ratio"] is not None else "n/a"
        flags = ", ".join(axis for axis in ("encode", "decode") if point[f"pareto_size_{axis}"]) or "—"
        table.append(f'<tr><th scope="row"><span style="color:{color}">{index+1} · {label}</span></th><td>{point["output_bytes"]:,}</td><td>{ratio}</td><td>{point["encode"]["median_ns"]/1e6:.3f}</td><td>{point["decode"]["median_ns"]/1e6:.3f}</td><td>{point["encode"]["p95_ns"]/1e6:.3f}</td><td>{point["encode"]["cv"]:.1%}</td><td>{flags}</td></tr>')
        file_rows = []
        for file in item["files"]:
            file_rows.append(f'<tr><th scope="row">{esc(file["path"])}</th><td>{file["input_bytes"]:,}</td><td>{file["output_bytes"]:,}</td><td>{file["encode"]["median_ns"]/1e6:.3f}</td><td>{file["decode"]["median_ns"]/1e6:.3f}</td><td><code>{esc(file["input_sha256"])}</code></td></tr>')
        details.append(f'<details><summary>{label} — per-file measurements and verified input hashes</summary><div class="scroll"><table><thead><tr><th>File</th><th>Input bytes</th><th>Output bytes</th><th>Encode ms</th><th>Decode ms</th><th>SHA256</th></tr></thead><tbody>{"".join(file_rows)}</tbody></table></div></details>')
    method = report["method"]
    corpus = report["corpus"]
    provenance = {key: report[key] for key in ("tool", "created_utc", "environment", "method", "corpus")}
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<title>Compression Observatory — measured lossless codecs</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f3f1eb;color:#192d35;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:48px 24px}}h1{{font-size:clamp(2rem,6vw,3.8rem);line-height:1.1;letter-spacing:-.04em;margin:12px 0}}h2{{font-size:1.35rem}}.eyebrow{{font-size:.8rem;letter-spacing:.13em;text-transform:uppercase;color:#007f79;font-weight:750}}.lede{{max-width:780px;color:#48616a}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:28px 0}}.card{{padding:18px 24px;background:#fff;border:1px solid #d9e0dc;border-radius:14px;flex:1;min-width:180px}}.card strong{{display:block;font-size:1.65rem}}section{{margin-top:34px}}.panel{{background:white;padding:24px;border-radius:16px;border:1px solid #d9e0dc}}svg{{width:100%;height:auto}}svg text{{font:13px system-ui,sans-serif}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:.88rem}}th,td{{padding:12px;text-align:right;border-bottom:1px solid #dce4e3;white-space:nowrap}}th:first-child{{text-align:left}}thead{{color:#48616a}}details{{margin:14px 0;padding:16px;background:white;border-radius:12px;border:1px solid #d9e0dc}}summary{{cursor:pointer;font-weight:650}}pre{{overflow:auto;font-size:.78rem;white-space:pre-wrap;overflow-wrap:anywhere}}code{{font-size:.75rem}}footer{{margin-top:36px;color:#48616a;font-size:.9rem}}</style></head>
<body><main><div class="eyebrow">Reproducible experiments · stdlib codecs</div><h1>Compression Observatory</h1><p class="lede">A byte-verified lossless compression experiment. Each file is compressed independently. These measurements describe this corpus and environment; they establish no general codec ranking or private research result.</p>
<div class="cards"><div class="card">Input size<strong>{corpus["input_bytes"]:,} B</strong>{corpus["file_count"]} files</div><div class="card">Measured repetitions<strong>{method["measured_repeats"]}</strong>{method["warmups_per_file_codec"]} warmups per file / codec</div><div class="card">Byte-exact round trips<strong>All verified</strong>Equality + SHA256 on every iteration</div></div>
<section class="panel"><h2>Size / encode time tradeoff</h2><p>Lower and farther left is better. Numbered markers match the table below, which provides exact values. Linear axes, median aggregate call times.</p><svg viewBox="0 0 880 400" role="img" aria-label="Scatter plot comparing compressed bytes and median encode time"><path d="M80 50V325H800" fill="none" stroke="#9db1b5"/><text x="80" y="350">0</text><text x="650" y="350">{max_size:,} B</text><text x="320" y="385">Compressed bytes →</text><text x="8" y="38">Encode ms ↑</text><text x="5" y="75">{max_time/1e6:.2f}</text><text x="50" y="325">0</text>{"".join(dots)}</svg></section>
<section><h2>Aggregate measurements</h2><p>Ratio = total compressed bytes ÷ total input bytes (lower is smaller). Pareto marks size/time pairs that no measured configuration dominates; ties remain on the frontier. A frontier is not a statistical significance test.</p><div class="panel scroll"><table><thead><tr><th>Codec : level</th><th>Output B</th><th>Ratio</th><th>Encode ms</th><th>Decode ms</th><th>Encode p95 ms</th><th>Encode CV</th><th>Size / time Pareto</th></tr></thead><tbody>{"".join(table)}</tbody></table></div></section>
<section><h2>Inspect individual files</h2>{"".join(details)}</section><section><h2>Provenance &amp; measurement policy</h2><p>Times exclude disk I/O, hashing and validation. No memory/peak-RSS measurements. Serial execution, fixed order, warm process. Short samples, background activity, library versions and CPU conditions can affect results. Raw repeats and both timing distributions are in the JSON companion.</p><details><summary>Source fingerprints, corpus manifest, environment and policy</summary><pre>{esc(json.dumps(provenance, indent=2, ensure_ascii=False))}</pre></details></section><footer>Generated by Compression Observatory {esc(report["tool"]["version"])} · {esc(report["created_utc"])} · Self-contained report: no external assets, scripts or tracking.</footer></main></body></html>'''
