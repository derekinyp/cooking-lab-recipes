#!/usr/bin/env python3
"""補寫批次：用 codex exec 一次處理一批菜，輸出 JSON 存檔。
用法：python3 tools/backfill_run.py <批次名> <菜代號…>
紀錄：/workspace/cooking-system/backfill-runs/calls.jsonl（每呼叫一次一行，供用量稽核）"""
import json, subprocess, sys, time, datetime, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import backfill_context as BC
RUNS = Path('/workspace/cooking-system/backfill-runs'); RUNS.mkdir(parents=True, exist_ok=True)
CAP = 20

def used():
    f = RUNS / 'calls.jsonl'
    return sum(1 for _ in f.open()) if f.exists() else 0

def main():
    name, rids = sys.argv[1], sys.argv[2:]
    if used() >= CAP: sys.exit(f'外部呼叫已達上限 {CAP}，停止')
    tpl = (ROOT / 'tools' / 'backfill_prompt.md').read_text(encoding='utf-8')
    defaults = (ROOT / 'vocab' / 'backfill_defaults.yaml').read_text(encoding='utf-8')
    ctx = '\n\n'.join(f'### 菜代號：{r}\n' + json.dumps(BC.context(r), ensure_ascii=False, default=str) for r in rids)
    import os
    tpl = tpl.replace('## 補寫常識表', os.environ.get('EXTRA', '') + '\n\n## 補寫常識表')
    prompt = tpl.replace('{N}', str(len(rids))).replace('{DEFAULTS}', defaults).replace('{CONTEXTS}', ctx)
    (RUNS / f'{name}.prompt.txt').write_text(prompt, encoding='utf-8')
    out = RUNS / f'{name}.out.txt'; err = RUNS / f'{name}.err.txt'
    t0 = time.time()
    cmd = ['codex', 'exec', '--skip-git-repo-check', '-s', 'read-only', '-c', 'approval_policy="never"', '-o', str(out), '-']
    env = {'PATH': '/home/box/.local/bin:/usr/local/bin:/usr/bin:/bin', 'HOME': '/home/box'}
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1500, env=env, cwd='/tmp')
    err.write_text(p.stderr[-4000:], encoding='utf-8')
    toks = ''
    for l in p.stderr.splitlines()[-6:]:
        if 'tokens used' in l.lower(): toks = l.strip()
    rec = {'batch': name, 'rids': rids, 'time': datetime.datetime.now().isoformat(timespec='seconds'), 'sec': round(time.time() - t0), 'exit': p.returncode,
           'model': 'gpt-6-luna(medium)', 'prompt_chars': len(prompt), 'out_chars': len(out.read_text(encoding='utf-8')) if out.exists() else 0, 'tokens': toks}
    with (RUNS / 'calls.jsonl').open('a', encoding='utf-8') as f: f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(json.dumps(rec, ensure_ascii=False))
main()
