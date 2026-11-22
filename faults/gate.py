"""CI gate: fail if the committed exam results fall below the floor in docs/gate.json.

The exam needs the whole Shop and paid model calls, so it runs locally (faults/exam.sh) and its summary
is committed as docs/results.json. Comparing with the previous numbers was wrong: adding honest new
runs lowered the average and failed the gate. So the gate checks a fixed floor, raised on purpose
when the agent improves, and a change that drops the standard condition below it cannot merge.

Usage: python faults/gate.py
"""

import json
import sys

floor = json.load(open("docs/gate.json"))
r = json.load(open("docs/results.json"))["modes"]["standard"]
pass4 = r["pass4"] / r["incidents"]
print(f"accuracy {r['accuracy']:.1%} (floor {floor['min_accuracy']:.0%}); "
      f"pass^4 {pass4:.1%} (floor {floor['min_pass4']:.0%}); {r['incidents']} incidents")
if r["accuracy"] < floor["min_accuracy"] or pass4 < floor["min_pass4"]:
    sys.exit("FAIL: the agent is below the floor")
print("PASS")
