#!/usr/bin/env python3
"""驗證並套用補寫結果。
用法：python3 tools/backfill_apply.py <批次輸出檔> [--apply] [--only 菜代號…]
不加 --apply 只驗證（回報每道菜的問題）。通過驗證的菜才會被寫入；有問題的整道不寫，印出原因讓人處理。
規則：
 - 來源有寫的值不覆蓋（已有數字的材料、已有秒數的步驟、已有檔位的火候）
 - 補的值一律 status: inferred，依據寫進 note（「補寫依據：…」）
 - 食安數字只能是 USDA 表（63／71／74 °C）或配方檔原本就有的數字
 - 對外文字不得有過程用語、大陸用語、英文單字；用到的數字必須在配方檔（含依據）找得到
"""
import copy, datetime, io, json, re, sys, yaml
from pathlib import Path
from ruamel.yaml import YAML
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import apply_tw_terms as TWA
TW = yaml.safe_load((ROOT / 'vocab' / 'tw_terms.yaml').read_text(encoding='utf-8'))
HEATS = {l['id'] for l in yaml.safe_load((ROOT / 'vocab' / 'heat.yaml').read_text(encoding='utf-8'))['levels']}
UNITS = {u['id'] for u in yaml.safe_load((ROOT / 'vocab' / 'units.yaml').read_text(encoding='utf-8'))['units']}
SAFE_C = {63, 71, 74}
FORB = re.compile('|'.join(map(re.escape, TW['forbidden_phrases'])) + r'|沒寫|未寫|未給|未註明|來源|依據|\bS\d\b|\bM\b')
CN = re.compile('|'.join(t.get('rx') or re.escape(t['cn']) for t in TW['terms']))
NUM = re.compile(r'\d+(?:\.\d+)?')
TODAY = '2026-11-28'

def yml():
    y = YAML(); y.preserve_quotes = True; y.indent(mapping=2, sequence=4, offset=2); y.width = 4096
    y.representer.add_representer(type(None), lambda r, d: r.represent_scalar('tag:yaml.org,2002:null', 'null'))
    return y

def parse_out(path):
    """逐道菜解析：某一道的 JSON 壞掉只影響那一道（回報 decision: bad_json），其他照常。"""
    t = Path(path).read_text(encoding='utf-8').strip()
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t)
    try:
        i = t.index('{'); j = t.rindex('}')
        return json.loads(t[i:j + 1])
    except Exception:
        pass
    ms = list(re.finditer(r'"([a-z0-9_]+)"\s*:\s*\{\s*"decision"', t))
    out = {}; dec = json.JSONDecoder()
    for k, m in enumerate(ms):
        a = t.index('{', m.end(1))
        seg_end = ms[k + 1].start() if k + 1 < len(ms) else len(t)
        seg = re.sub(r'[,\s]+$', '', t[a:seg_end])
        obj = None
        cands = [seg] + [seg + '}' * n for n in (1, 2)]          # 常見：少一個右括號
        cands += [seg[:len(seg) - n] for n in range(1, 4) if seg.endswith('}' * n)]   # 最後一道：結尾多了外層的右括號
        for c in cands:
            try: obj = json.loads(c); break
            except Exception: pass
        out[m.group(1)] = obj if obj is not None else {'decision': 'bad_json'}
    return out

def strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for v in o.values(): yield from strings(v)
    elif isinstance(o, list):
        for v in o: yield from strings(v)

def sanitize(p, old=None, ids=None):
    """機械可修的小問題直接修（不必再問外部模型）：步驟的 tool 填成詞表 id 就拿掉（系統會用詞表的中文名）。"""
    ov = p.get('overlay') or {}
    for sid, st in list((ov.get('steps') or {}).items()):
        if isinstance(st, dict) and isinstance(st.get('tool'), str) and re.match(r'^tool/', st['tool']): del st['tool']
    for k in ('tag', 'tag_note', 'missing'): ov.pop(k, None)
    if ids is not None and p.get('text_fixes'):        # 外部模型寫錯 id 的修正項直接略過（留給建置掃描與人工補）
        p['text_fixes'] = [f for f in p['text_fixes'] if f.get('id') in ids]
    for a in (p.get('actions') or {}).values():     # 0 秒＝瞬間完成的步驟，不需要秒數
        if a.get('min_s') == 0 and a.get('max_s') == 0: a['min_s'] = a['max_s'] = None
    for k in ('tools', 'tool_alts', 'states', 'two_serving'):      # 外部模型常把這些清空；原本有的就沿用原本的
        if (old or {}).get(k) and (not ov.get(k) or isinstance(ov.get(k), list)): ov[k] = old[k]
    # 目測量（ing）：只沿用原本乾淨的 suggest／confirmed，其餘過程說明不要
    oi = {}
    for iid, v in ((old or {}).get('ing') or {}).items():
        t = (v or {}).get('confirmed') or (v or {}).get('suggest')
        if t and not FORB.search(t) and not CN.search(t): oi[iid] = {'suggest': t}
    ing = ov.get('ing') if isinstance(ov.get('ing'), dict) else {}
    ov['ing'] = {**oi, **ing}
    if isinstance(ov.get('tools'), list) or isinstance(ov.get('tool_alts'), list):
        for k in ('tools', 'tool_alts'):
            if isinstance(ov.get(k), list): ov.pop(k)    # 應該是 {詞表 id: 中文名}；給成清單就拿掉，系統會用詞表的中文名
    return p

def public_strings(p):
    """會顯示給使用者的字：overlay 全部（不含 spice.mode）、completion 的 observe/target、sensory、text_fixes。"""
    ov = {k: v for k, v in (p.get('overlay') or {}).items() if k != 'spice'}
    sp = dict(((p.get('overlay') or {}).get('spice') or {})); sp.pop('mode', None)
    out = list(strings(ov)) + list(strings(sp))
    for v in (p.get('completion') or {}).values():
        for c in v or []: out += [c.get('observe', ''), c.get('target', '')]
    s = p.get('serving') or {}
    out += [(s.get('temp_and_hold') or {}).get('target', '')] + list(((s.get('sensory') or {}).values()))
    out += [f.get('new', '') for f in p.get('text_fixes') or []]
    return [x for x in out if isinstance(x, str)]

def validate(rid, p, d, raw_before):
    errs = []
    if p.get('decision') == 'park': return errs
    if p.get('decision') == 'bad_json': return ['這道菜的 JSON 格式壞掉，需要重問']
    if p.get('decision') != 'ok': return ['decision 必須是 ok 或 park']
    g = {i['id']: i for i in d['ingredients']}; acts = {a['id']: a for a in d['actions']}
    if p.get('servings'):
        v = p['servings'].get('value')
        if not isinstance(v, int) or not 1 <= v <= 12: errs.append(f'份數不合理：{v}')
        if not p['servings'].get('basis'): errs.append('份數沒有依據')
    t = p.get('time') or {}
    if not isinstance(t.get('total_min'), int) or not 5 <= t['total_min'] <= 720: errs.append(f'總時間不合理：{t.get("total_min")}')
    if not t.get('basis'): errs.append('總時間沒有依據')
    for iid, q in (p.get('ingredients') or {}).items():
        if iid not in g: errs.append(f'沒有這個材料 id：{iid}'); continue
        if not isinstance(q.get('value'), (int, float)) or q['value'] <= 0: errs.append(f'{iid} 數量不合理：{q.get("value")}')
        if q.get('unit') not in UNITS: errs.append(f'{iid} 單位不在詞表：{q.get("unit")}')
        if not q.get('basis'): errs.append(f'{iid} 沒有依據')
    for aid, a in (p.get('actions') or {}).items():
        if aid not in acts: errs.append(f'沒有這個步驟 id：{aid}'); continue
        h = a.get('heat')
        if h and h not in HEATS: errs.append(f'{aid} 火候不在詞表：{h}')
        lo, hi = a.get('min_s'), a.get('max_s')
        if (lo is None) != (hi is None): errs.append(f'{aid} 秒數要成對')
        if lo is not None and not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and 0 < lo <= hi <= 43200): errs.append(f'{aid} 秒數不合理：{lo}–{hi}')
        if not a.get('basis'): errs.append(f'{aid} 沒有依據')
    for aid in (p.get('completion') or {}):
        if aid not in acts: errs.append(f'completion 沒有這個步驟 id：{aid}')
    for f in p.get('text_fixes') or []:
        if f.get('id') not in g and f.get('id') not in acts: errs.append(f'text_fixes 沒有這個 id：{f.get("id")}')
        if f.get('field') not in ('label', 'term'): errs.append(f'text_fixes 欄位不對：{f.get("field")}')
    # 食安數字
    for s in list(strings(p)):
        for n in re.findall(r'(\d+)\s*(?:°C|℃|度)', s):
            if int(n) not in SAFE_C and n not in NUM.findall(raw_before): errs.append(f'食安溫度 {n}°C 不在 USDA 表也不在來源：{s[:40]}')
    # 對外文字
    for s in public_strings(p):
        if FORB.search(s): errs.append(f'對外文字有過程用語：{s[:50]}')
        if CN.search(s): errs.append(f'對外文字有大陸用語：{s[:50]}')
        if re.search(r'[A-Za-z]{3,}', s): errs.append(f'對外文字有英文：{s[:50]}')
    ov = p.get('overlay')
    if not isinstance(ov, dict): errs.append('缺 overlay')
    else:
        for k in ('intro', 'card', 'burners', 'spice'):
            if not ov.get(k): errs.append(f'overlay 缺 {k}')
        sp = ov.get('spice') or {}
        if sp.get('mode') not in ('none', 'addon', 'separate'): errs.append(f'spice.mode 不對：{sp.get("mode")}')
        for bad in ('tag', 'tag_note', 'missing'):
            if bad in ov: errs.append(f'overlay 不該有 {bad}')
        if len(ov.get('card', '')) < 12: errs.append('card 太短')
        if len(ov.get('intro', '')) < 12: errs.append('intro 太短')
    return errs

def note_add(old, new):
    return (str(old).rstrip('；。 ') + '；' if old else '') + new

def apply_doc(doc, p):
    r = doc['recipe']; iid_map = {i['id']: i for i in doc['ingredients']}; act_map = {a['id']: a for a in doc['actions']}
    filled = {'servings': 0, 'time': 1, 'ingredients': 0, 'duration': 0, 'heat': 0, 'completion': 0, 'sensory': 0, 'serving': 0, 'text_fixes': 0}
    sv = p.get('servings')
    if sv and not (r.get('servings') or {}).get('value'):
        r['servings'] = {'value': sv['value'], 'status': 'inferred', 'note': f'補寫依據：{sv["basis"]}'}; filled['servings'] = 1
    notes = doc.setdefault('notes', {})
    t = p['time']
    notes['total_min'] = str(t['total_min']); notes['time_basis'] = t['basis']
    if t.get('prep_ahead'): notes['prep_ahead'] = t['prep_ahead']
    for k in ('weekday', 'missing'):
        if k in notes: notes[k] = '已補寫（2026-11-28）：份量、時間、火候、用量的補寫依據見 notes.time_basis 與各欄位 note'
    for iid, q in (p.get('ingredients') or {}).items():
        ing = iid_map[iid]; qt = ing['qty']
        if qt.get('value') is not None or qt.get('min') is not None or qt.get('max') is not None: continue
        qt['value'] = q['value']; qt['unit'] = q['unit']; qt['status'] = 'inferred'; qt.pop('qualitative', None)   # 「少許」留在 raw_text
        qt['note'] = note_add(qt.get('note'), f'補寫依據：{q["basis"]}'); filled['ingredients'] += 1
    for aid, a in (p.get('actions') or {}).items():
        act = act_map[aid]; pr = act.setdefault('params', {}); basis = []
        h = a.get('heat'); hp = pr.get('heat')
        if h and not (hp or {}).get('level'):
            if hp is None: pr['heat'] = {'level': h, 'raw': None, 'evidence': None}
            else: hp['level'] = h; hp['raw'] = None
            filled['heat'] += 1; basis.append(a['basis'])
        du = pr.get('duration')
        if a.get('min_s') is not None and (du is None or (du.get('min_s') is None and du.get('max_s') is None)):
            pr['duration'] = {'min_s': a['min_s'], 'max_s': a['max_s'], 'raw': None, 'is_guide': True, 'evidence': None, 'status': 'inferred'}
            filled['duration'] += 1; basis.append(a['basis'])
        if basis: act['note'] = note_add(act.get('note'), '補寫依據：' + basis[0])
    for aid, comps in (p.get('completion') or {}).items():
        act = act_map[aid]
        act['completion'] = [{'observe': c['observe'], 'target': c['target'], 'method': '目測', 'evidence': None} for c in comps]
        filled['completion'] += 1
    sv_ = p.get('serving') or {}
    srv = doc.setdefault('serving', {}); comp = srv.setdefault('completion', [])
    th = sv_.get('temp_and_hold')
    if th:
        hit = False
        for c in comp:
            if re.search(r'沒寫|未寫|推論|不明', str(c.get('target') or '')) :
                c['target'] = th['target']; c['method'] = None; c['evidence'] = None; c['note'] = '補寫依據：' + th['basis']; hit = True; filled['serving'] += 1; break
        if not hit:
            comp.append({'observe': '上桌溫度與時限', 'target': th['target'], 'method': None, 'evidence': None, 'note': '補寫依據：' + th['basis']}); filled['serving'] += 1
    st = srv.setdefault('sensory_target', {})
    for k, v in (sv_.get('sensory') or {}).items():
        if k in ('color', 'taste', 'texture') and (not st.get(k) or re.search(r'沒寫|未寫|不明|推論', str(st.get(k)))):
            st[k] = v; filled['sensory'] += 1
    for f in p.get('text_fixes') or []:
        tgt = iid_map.get(f['id']) or act_map.get(f['id'])
        tgt[f['field']] = f['new']; filled['text_fixes'] += 1
    # 紀錄
    r['version'] = '1.1'
    if not any(c.get('version') == '1.1' and str(c.get('date')) == TODAY and c.get('by') == 'codex' for c in r['changelog']):
      r['changelog'].append({'version': '1.1', 'date': TODAY, 'change': '補寫缺少的份量、時間、火候、用量與成品樣子（status: inferred，依據見各欄位 note）；台灣用語；對外說明改寫', 'by': 'codex'})
    return filled

def run(path, do_apply, only):
    out = parse_out(path); report = {}
    y = yml()
    for rid, p in out.items():
        if only and rid not in only: continue
        f = next((ROOT / 'recipes').glob(f'{rid}.*.yaml'))
        raw = f.read_text(encoding='utf-8')
        d = yaml.safe_load(raw)
        oldp = ROOT / 'site' / 'content' / f.name
        p = sanitize(p, yaml.safe_load(oldp.read_text(encoding='utf-8')) if oldp.exists() else {}, {x['id'] for x in d['ingredients']} | {x['id'] for x in d['actions']})
        errs = validate(rid, p, d, raw)
        if not errs and p.get('decision') == 'ok':
            doc = y.load(raw); filled = apply_doc(doc, p)
            buf = io.StringIO(); y.dump(doc, buf); new = buf.getvalue()
            ov = {k: v for k, v in copy.deepcopy(p['overlay']).items() if v not in (None, [], {}, '')}   # 空的欄位不寫
            ovtext = yaml.safe_dump(ov, allow_unicode=True, sort_keys=False, width=4096)
            src_nums = set(NUM.findall(new))
            bad = sorted({n for n in NUM.findall(ovtext) if n not in src_nums and n not in ('1', '2')})
            usda = [n for n in bad if n.isdigit() and int(n) in SAFE_C]
            if usda and len(usda) == len(bad):     # 對外文字用到 USDA 食安溫度，但依據沒寫進去：補一條依據，不必再問模型
                doc['notes']['food_safety_basis'] = '對外文字用到的溫度 ' + '、'.join(f'{n}°C' for n in usda) + '：' + '美國農業部（USDA）食品安全安全內部溫度表（禽肉 74、絞肉 71、整塊肉與魚貝 63）'
                buf = io.StringIO(); y.dump(doc, buf); new = buf.getvalue(); bad = []
            if bad: errs.append(f'對外文字的數字在配方檔找不到（要寫進補寫依據）：{bad}')
            else:
                # 只有結構相同才算數：讀回來比對
                chk = yaml.safe_load(new)
                if len(chk['actions']) != len(d['actions']) or len(chk['ingredients']) != len(d['ingredients']): errs.append('動作或材料數量變了')
            if not errs:
                report[rid] = {'status': 'ok', 'filled': filled}
                if do_apply:
                    f.write_text(new, encoding='utf-8')
                    (ROOT / 'site' / 'content' / f.name).write_text(ovtext, encoding='utf-8')
                continue
        if p.get('decision') == 'park':
            report[rid] = {'status': 'park', 'reason': p.get('park_reason')}; continue
        report[rid] = {'status': 'error', 'errors': errs}
    return report

if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    only = []
    if '--only' in sys.argv: only = sys.argv[sys.argv.index('--only') + 1:]; a = [x for x in a if x not in only]
    rep = run(a[0], '--apply' in sys.argv, only)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
