#!/usr/bin/env python3
"""把一道菜「缺什麼」整理成一份簡短內容，交給外部模型補寫。也用來盤點（--inventory）。"""
import json, re, sys, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
MARK = re.compile(r'沒寫|未寫|未提供|未註明|推論|不明|待試做|無法')

def load(rid_prefix):
    p = next((ROOT / 'recipes').glob(f'{rid_prefix}.*.yaml'))
    d = yaml.safe_load(p.read_text(encoding='utf-8'))
    c = ROOT / 'site' / 'content' / p.name
    ov = yaml.safe_load(c.read_text(encoding='utf-8')) if c.exists() else {}
    return p, d, ov or {}

def gaps(d):
    r = d['recipe']; g = {'servings': not (r.get('servings') or {}).get('value')}
    g['total_min'] = not ((d.get('notes') or {}).get('total_min'))
    g['ing_no_qty'] = [i['id'] for i in d['ingredients'] if (i['qty'].get('value') is None and i['qty'].get('min') is None and i['qty'].get('max') is None)]
    acts = d['actions']
    g['no_duration'] = [a['id'] for a in acts if not (a.get('params') or {}).get('duration') or ((a['params']['duration'].get('min_s') is None and a['params']['duration'].get('max_s') is None))]
    heat_needed = [a['id'] for a in acts if a.get('tool') in ('tool/wok', 'tool/pan', 'tool/stock_pot', 'tool/pot', 'tool/saucepan', 'tool/clay_pot', 'tool/steamer', 'tool/electric_cooker', 'tool/skillet') or (a.get('params') or {}).get('heat') is not None]
    g['no_heat'] = [i for i in heat_needed if not ((next(a for a in acts if a['id'] == i).get('params') or {}).get('heat') or {}).get('level')]
    sv = d.get('serving') or {}
    g['serving_missing'] = sum(1 for c in sv.get('completion') or [] if MARK.search(str(c.get('target') or '')))
    g['sensory_missing'] = [k for k, v in (sv.get('sensory_target') or {}).items() if MARK.search(str(v))]
    return g

def context(rid_prefix):
    p, d, ov = load(rid_prefix)
    r = d['recipe']
    out = {'file': p.name, 'name': r['name']['zh_hant'], 'variant': r.get('variant'), 'summary': r.get('summary'),
           'servings': r.get('servings'), 'sources': [{'id': s['id'], 'title': s['title'], 'note': s.get('note')} for s in r['sources']],
           'ingredients': [{'id': i['id'], 'label': i['label'], 'role': i.get('role'), 'qty': {k: v for k, v in i['qty'].items() if k in ('value', 'min', 'max', 'unit', 'qualitative', 'raw_text', 'status', 'note')}} for i in d['ingredients']],
           'actions': [], 'serving': d.get('serving'), 'notes': {k: v for k, v in (d.get('notes') or {}).items() if k in ('weekday', 'burners', 'compare', 'missing', 'no_scale', 'spicy_split')},
           'gaps': gaps(d), 'public_overlay': ov}
    for a in d['actions']:
        pr = a.get('params') or {}
        out['actions'].append({'id': a['id'], 'technique': a.get('technique'), 'term': a.get('term'), 'tool': a.get('tool'), 'inputs': a.get('inputs'),
                               'heat': pr.get('heat'), 'duration': pr.get('duration'), 'temperature': pr.get('temperature'),
                               'completion': a.get('completion'), 'note': a.get('note')})
    return out

if __name__ == '__main__':
    if '--inventory' in sys.argv:
        tot = {'dishes': 0, 'servings': 0, 'total_min': 0, 'ing_no_qty': 0, 'ings': 0, 'no_duration': 0, 'no_heat': 0, 'acts': 0, 'serving_missing': 0}
        for p in sorted((ROOT / 'recipes').glob('*.yaml')):
            d = yaml.safe_load(p.read_text(encoding='utf-8')); g = gaps(d)
            tot['dishes'] += 1; tot['servings'] += g['servings']; tot['total_min'] += g['total_min']
            tot['ing_no_qty'] += len(g['ing_no_qty']); tot['ings'] += len(d['ingredients'])
            tot['no_duration'] += len(g['no_duration']); tot['no_heat'] += len(g['no_heat']); tot['acts'] += len(d['actions']); tot['serving_missing'] += g['serving_missing']
            if '--each' in sys.argv: print(p.name.split('.')[0], {k: (len(v) if isinstance(v, list) else v) for k, v in g.items()})
        print(json.dumps(tot, ensure_ascii=False))
    else:
        print(json.dumps(context(sys.argv[1]), ensure_ascii=False, indent=1, default=str))
