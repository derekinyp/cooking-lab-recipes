#!/usr/bin/env python3
"""依序跑批次：呼叫外部模型 → 驗證 → 通過的馬上套用。同一類錯誤連續兩批都出現就停下來（要先修根因，不要一直燒算力）。"""
import json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import backfill_apply as BA
RUNS = Path('/workspace/cooking-system/backfill-runs')
batches = json.load(open('/tmp/batches.json'))
start, end = int(sys.argv[1]), int(sys.argv[2])
def kinds(rep):
    ks = set()
    for r in rep.values():
        for e in r.get('errors', []): ks.add(re.sub(r'[「『][^」』]*[」』]|\d+|[A-Za-z_./]+|：.*', '', e)[:14])
    return ks
prev = set()
for n in range(start, end + 1):
    name = f'b{n:02d}'; rids = batches[n - 1]
    r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'backfill_run.py'), name] + rids, capture_output=True, text=True)
    print(name, r.stdout.strip()[:300], r.stderr.strip()[-300:], flush=True)
    out = RUNS / f'{name}.out.txt'
    try: rep = BA.run(out, True, [])
    except Exception as e:
        print(name, '解析失敗：', repr(e)[:200], flush=True); k = {'解析失敗'}
        if k & prev: print('同一類錯誤連續兩批，停止'); break
        prev = k; continue
    (RUNS / f'{name}.report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = [k for k, v in rep.items() if v['status'] == 'ok']; bad = {k: v for k, v in rep.items() if v['status'] == 'error'}; park = [k for k, v in rep.items() if v['status'] == 'park']
    print(name, f'套用 {len(ok)}、錯誤 {len(bad)}、停放 {len(park)}', flush=True)
    k = kinds(rep)
    if k and k & prev: print('同一類錯誤連續兩批都出現，停止：', k, flush=True); break
    prev = k
