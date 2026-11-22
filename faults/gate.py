"""CI gate: fail if the committed exam results got worse than on the base branch.

The exam needs the whole Shop and paid model calls, so it runs locally (faults/exam.sh) and its summary
is committed as docs/results.json. This gate compares that file with the base branch's copy and fails
when accuracy or pass^4 drops, so a change that makes the agent worse cannot be merged quietly.

Usage: python faults/gate.py [base_ref]   (default origin/main)
"""

import json
import subprocess
import sys

base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
new = json.load(open("docs/results.json"))["modes"]["standard"]
try:
    old_text = subprocess.run(["git", "show", f"{base_ref}:docs/results.json"], check=True,
                              capture_output=True, text=True).stdout
    modes = json.loads(old_text)["modes"]
    old = modes.get("standard") or modes["off"]  # older results files called it "off"
except (subprocess.CalledProcessError, KeyError):
    print(f"no results on {base_ref} to compare with; gate passes")
    sys.exit(0)

new_pass4, old_pass4 = new["pass4"] / new["incidents"], old["pass4"] / old["incidents"]
print(f"accuracy {old['accuracy']:.1%} -> {new['accuracy']:.1%}; pass^4 {old_pass4:.1%} -> {new_pass4:.1%}")
if new["accuracy"] < old["accuracy"] or new_pass4 < old_pass4:
    sys.exit("FAIL: the agent got worse than on the base branch")
print("PASS")
