"""Add up the suite's jsonl files: totals per module, and the failures grouped by (group, check) with the pages they hit.

    python tools/qa/mobile_suite/summarize.py [glob-prefix]
"""
import collections
import json
import pathlib
import re
import sys

OUT = pathlib.Path(__file__).resolve().parents[3] / "tools" / "qa" / ".mobile" / "suite"
prefix = sys.argv[1] if len(sys.argv) > 1 else ""
mods = collections.defaultdict(lambda: [0, 0])
fails = collections.defaultdict(list)
groups = collections.Counter()
for f in sorted(OUT.glob(f"{prefix}*.jsonl")):
    mod = re.sub(r"-\d+$", "", f.stem)
    for line in f.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        mods[mod][0] += 1
        groups[r["g"]] += 1
        if not r["ok"]:
            mods[mod][1] += 1
            key = (r["g"], re.sub(r"^[^ ]*@[\dx@]+ ", "", r["n"]))
            fails[key].append((r["n"].split(" ")[0], r["d"]))
tot = sum(v[0] for v in mods.values())
bad = sum(v[1] for v in mods.values())
for m, (n, b) in mods.items():
    print(f"{m:22s} {n:6d} tests  {b:5d} failed")
print(f"{'TOTAL':22s} {tot:6d} tests  {bad:5d} failed   ({len(groups)} groups)")
print()
for (g, name), items in sorted(fails.items(), key=lambda kv: -len(kv[1])):
    pages = sorted({i[0].split("@")[0] for i in items})
    print(f"[{g}] {name}: {len(items)} fails on {len(pages)} pages/units   e.g. {items[0][0]} {items[0][1][:140]}")
