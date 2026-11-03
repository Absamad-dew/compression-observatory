"""Create the README's SVG summary from actual saved measurements (stdlib only)."""

from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / "examples/run.json").read_text(encoding="utf-8"))
rows = report["results"]
height = 300 + len(rows) * 58
lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 {height}" role="img" aria-label="Actual synthetic compression benchmark summary">',
         '<rect width="1100" height="100%" rx="24" fill="#f3f1eb"/>',
         '<g font-family="Arial, sans-serif" fill="#192d35">',
         '<text x="48" y="55" font-size="15" letter-spacing="3" fill="#007f79">STDLIB CODECS · BYTE-VERIFIED</text>',
         '<text x="48" y="112" font-size="44" font-weight="700">Compression Observatory</text>',
         f'<text x="48" y="150" font-size="18">Public synthetic corpus · {report["corpus"]["input_bytes"]:,} input bytes · {report["method"]["measured_repeats"]} measured repeats</text>',
         '<text x="48" y="206" font-size="15" fill="#48616a">CODEC / LEVEL</text>',
         '<text x="330" y="206" font-size="15" fill="#48616a">OUTPUT BYTES</text>',
         '<text x="570" y="206" font-size="15" fill="#48616a">RATIO</text>',
         '<text x="730" y="206" font-size="15" fill="#48616a">ENCODE ms</text>',
         '<text x="910" y="206" font-size="15" fill="#48616a">DECODE ms</text>']
for index, item in enumerate(rows):
    y = 247 + index * 58
    point = item["aggregate"]
    lines.extend([f'<rect x="32" y="{y-25}" width="1036" height="48" rx="10" fill="white"/>',
                  f'<text x="48" y="{y+6}" font-size="21" font-weight="600">{escape(item["codec"])}</text>',
                  f'<text x="330" y="{y+6}" font-size="21">{point["output_bytes"]:,}</text>',
                  f'<text x="570" y="{y+6}" font-size="21">{point["ratio"]:.4f}</text>',
                  f'<text x="730" y="{y+6}" font-size="21">{point["encode"]["median_ns"]/1e6:.3f}</text>',
                  f'<text x="910" y="{y+6}" font-size="21">{point["decode"]["median_ns"]/1e6:.3f}</text>'])
lines.extend([f'<text x="48" y="{height-26}" font-size="15" fill="#48616a">Measured example, not a general ranking · Raw repeats and source fingerprints in examples/run.json</text>', '</g></svg>'])
(ROOT / "examples/report-preview.svg").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
