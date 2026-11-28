#!/usr/bin/env python3
"""補寫摘要表：比對 git 的 HEAD（補寫前）和目前的食譜檔，列出每道菜補了哪些欄位、依據是什麼。輸出 Markdown。"""
import subprocess, sys, yaml, re, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
base = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
HZ = {l['id']: l['zh'] for l in yaml.safe_load((ROOT / 'vocab' / 'heat.yaml').read_text(encoding='utf-8'))['levels']}
UZ = {u['id']: u['zh'] for u in yaml.safe_load((ROOT / 'vocab' / 'units.yaml').read_text(encoding='utf-8'))['units']}
rows = []; parked = []
def basis(s):
    m = re.search(r'補寫依據：(.*)', str(s or '')); return m.group(1).strip() if m else ''
for p in sorted((ROOT / 'recipes').glob('*.yaml')):
    rid = p.name.split('.')[0]
    old = yaml.safe_load(subprocess.run(['git', 'show', f'{base}:recipes/{p.name}'], capture_output=True, text=True, cwd=ROOT).stdout)
    new = yaml.safe_load(p.read_text(encoding='utf-8'))
    if old == new: parked.append(rid); continue
    name = new['recipe']['name']['zh_hant']; f = []
    sv_o, sv_n = old['recipe'].get('servings') or {}, new['recipe'].get('servings') or {}
    if not sv_o.get('value') and sv_n.get('value'): f.append(('份量', f'{sv_n["value"]} 人份', basis(sv_n.get('note'))))
    n = new.get('notes') or {}
    if n.get('total_min'): f.append(('總時間', f'約 {n["total_min"]} 分鐘' + (f'；需先準備：{n["prep_ahead"]}' if n.get('prep_ahead') else ''), n.get('time_basis', '')))
    oi = {i['id']: i for i in old['ingredients']}
    for i in new['ingredients']:
        qo, qn = oi[i['id']]['qty'], i['qty']
        if qo.get('value') is None and qn.get('value') is not None: f.append((f'材料「{i["label"]}」', f'{qn["value"]} {UZ.get(qn.get("unit"), qn.get("unit"))}', basis(qn.get('note'))))
    oa = {a['id']: a for a in old['actions']}
    for a in new['actions']:
        po, pn = oa[a['id']].get('params') or {}, a.get('params') or {}
        parts = []
        if not (po.get('heat') or {}).get('level') and (pn.get('heat') or {}).get('level'): parts.append(f'火候 {HZ.get(pn["heat"]["level"], pn["heat"]["level"])}')
        do, dn = po.get('duration') or {}, pn.get('duration') or {}
        if do.get('min_s') is None and do.get('max_s') is None and (dn.get('min_s') is not None): parts.append('時間 ' + (f'{dn["min_s"]} 秒' if dn['min_s'] == dn['max_s'] else f'{dn["min_s"]}–{dn["max_s"]} 秒'))
        if parts: f.append((f'步驟 {a["id"]}（{str(a.get("term"))[:14]}）', '、'.join(parts), basis(a.get('note'))))
    cs = sum(1 for a in new['actions'] if (a.get('completion') or []) != (oa[a['id']].get('completion') or []))
    if cs: f.append(('好了的樣子', f'{cs} 個步驟改寫成具體描述', '依各步驟的做法與一般家庭做法'))
    so, sn = (old.get('serving') or {}).get('sensory_target') or {}, (new.get('serving') or {}).get('sensory_target') or {}
    ch = [k for k in sn if sn[k] != so.get(k)]
    if ch: f.append(('成品色香味', '、'.join(ch), '依各步驟的做法與食材'))
    th = [c for c in (new.get('serving') or {}).get('completion') or [] if basis(c.get('note'))]
    if th: f.append(('上桌溫度與時限', th[0]['target'], basis(th[0]['note'])))
    rows.append((rid, name, f))
out = ['# 補寫摘要表（2026-11-28）', '', f'共補寫 {len(rows)} 道。所有補的值在食譜檔標 `status: inferred`，依據寫在各欄位 `note`（總時間依據在 `notes.time_basis`）；來源有寫的數字沒有動。', '']
for rid, name, f in rows:
    out += [f'## {name}（{rid}）', '', '| 欄位 | 補的內容 | 依據 |', '|---|---|---|']
    for a, b, c in f: out.append(f'| {a} | {b} | {c.replace("|", "／")} |')
    out.append('')
tot = {'份量': 0, '總時間': 0, '材料': 0, '步驟（火候或時間）': 0, '好了的樣子': 0}
for _, _, f in rows:
    for a, b, c in f:
        k = '材料' if a.startswith('材料') else '步驟（火候或時間）' if a.startswith('步驟') else a
        if k in tot: tot[k] += 1
out += ['## 合計', '', '| 項目 | 筆數 |', '|---|---|'] + [f'| {k} | {v} |' for k, v in tot.items()]
Path(sys.argv[2] if len(sys.argv) > 2 else '/dev/stdout').write_text('\n'.join(out) + '\n', encoding='utf-8')
print(json.dumps({'dishes_filled': len(rows), 'not_changed': parked, **tot}, ensure_ascii=False))
