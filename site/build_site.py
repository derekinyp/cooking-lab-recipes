#!/usr/bin/env python3
"""食譜網站產生器：recipes/*.yaml（數字唯一來源）＋ site/content/*.yaml（白話說明，不含新數字）→ docs/ 靜態網站。
用法：python3 site/build_site.py            # 產生 docs/
      python3 site/build_site.py --fonts    # 另外重做字型子集（需要設計規範原始字型）
"""
import html, json, math, re, shutil, sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
OUT = ROOT / 'docs'
ASSET_VER = 'zd-1.2.1'
NOTION_URL = 'https://app.notion.com/p/41ee8f6a3d02815d8e0aff273621fa82'
E = lambda s: html.escape(str(s), quote=True)

try:
    import opencc
    _cc = opencc.OpenCC('s2tw')
    # 繁簡同形、會被誤轉的字（例：干二流芡→幹、一面→一麵），不拿來判斷「這句是簡體」
    _AMBIG = set('干台只面后里才余云准几布松占当着征斗冲借制系历丑咸签卷向苏范钟致游注采术朴姜升合谷了志郁据弦恶')
    def s2t(s):
        s = str(s)
        if any(c not in _AMBIG and _cc.convert(c) != c for c in s):
            s = _cc.convert(s)
        return s.replace('臺', '台')
except Exception:  # 沒有 opencc 就不轉
    s2t = lambda s: s

# ------------------------------------------------------------------ 詞表
def load_vocab():
    zh, facets = {}, {}
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get('id'), str) and 'zh' in o:
                zh[o['id']] = o['zh']
                if 'facets' in o: facets[o['id']] = o['facets']
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    for f in sorted((ROOT / 'vocab').glob('*.yaml')):
        walk(yaml.safe_load(f.read_text(encoding='utf-8')))
    return zh, facets
VZH, VFACET = load_vocab()

UNIT = {'g': '克', 'kg': '公斤', 'ml': '毫升', 'l': '公升', 'piece': '個', 'clove': '瓣', 'slice': '片', 'stalk': '根',
        'bicchiere': '杯', 'cucchiaio': '匙', 'tbsp': '大匙', 'tsp': '小匙', 'cup': '杯', 'pack': '包', 'mm': '毫米', 'cm': '公分'}
SPOONISH = {'piece', 'clove', 'slice', 'stalk', 'bicchiere', 'cucchiaio', 'tbsp', 'tsp', 'cup', 'pack'}
PIECE_WORD = [('蛋', '顆'), ('洋蔥', '顆'), ('番茄', '顆'), ('甜椒', '顆'), ('青椒', '顆'), ('紅蔥頭', '顆'), ('檸檬', '顆'),
              ('魚', '尾'), ('瑪芬', '個'), ('牛', '塊'), ('蔥', '根'), ('胡椒粒', '粒')]
BURNER_TOOLS = {'tool/wok', 'tool/frying_pan', 'tool/heavy_pot', 'tool/dutch_oven', 'tool/stock_pot', 'tool/clay_pot',
                'tool/saucepan', 'tool/bain_marie'}
LEVEL = {'A': '官方或教科書', 'B': '出版食譜', 'C': '網路食譜'}
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'
TAGS = {'weekday': ('平日可做（20 分鐘內）', 'ok', '●'), 'weekend': ('假日菜', 'na', '○'), 'pending': ('待試做計時', 'watch', '◐')}

FRAC = {0: '', 1/6: '⅙', 1/4: '¼', 1/3: '⅓', 1/2: '½', 2/3: '⅔', 3/4: '¾', 5/6: '⅚'}
def fmt_num(v, unit):
    """數字格式：匙、個這類用分數；克、毫升用整數或一位小數。"""
    if v is None: return None
    if unit in SPOONISH:
        whole = math.floor(v + 1e-9); rest = v - whole
        for f, g in FRAC.items():
            if abs(rest - f) < 0.02:
                if whole and g: return f'{whole}{g}'
                return g or str(whole)
            if abs(rest - 1) < 0.02: return str(whole + 1)
        return f'{v:.2f}'.rstrip('0').rstrip('.')
    if v >= 10: return str(int(round(v)))
    s = f'{v:.1f}'.rstrip('0').rstrip('.')
    return s

def unit_word(unit, label=''):
    if unit == 'piece':
        for k, w in PIECE_WORD:
            if k in label: return w
    return UNIT.get(unit, '')

# ------------------------------------------------------------------ 文字清理
LATIN_PAREN = re.compile(r'[（(][^（）()]*[A-Za-z][^（）()]*[）)]')
def make_cleaner(srcmap):
    code_re = re.compile(r'(?<![A-Za-z0-9])(' + '|'.join(sorted(map(re.escape, srcmap), key=len, reverse=True)) + r')(?![A-Za-z0-9])') if srcmap else None
    def clean(s):
        if s is None: return None
        s = s2t(str(s))
        s = LATIN_PAREN.sub('', s)
        if code_re: s = code_re.sub(lambda m: '來源' + srcmap[m.group(1)], s)
        s = s.replace('℃', '°C')
        s = re.sub(r'(?<=[\d\s])cm\b', '公分', s); s = re.sub(r'(?<=[\d\s])mm\b', '毫米', s); s = re.sub(r'(?<=[\d\s])m[lL]\b', '毫升', s)
        s = re.sub(r'\s+(?=[公毫])', ' ', s)
        s = re.sub(r'(公分|毫米|毫升) (?=[\u4e00-\u9fff])', r'\1', s)
        s = re.sub(r'(?:見)?(?:表|附錄) ?[A-Z]?\.?\d+(?:\.\d+)*(?: ?注 ?[a-z])?(?:[／/] ?注 ?[a-z])*', '原文', s)
        s = re.sub(r'(?:見)?標準 ?\d+(?:\.\d+)+', '原文', s)
        s = s.replace('原文：原文', '原文')
        return s.strip()
    return clean

# ------------------------------------------------------------------ 食譜攤平
def flatten(d, comp=None, depth=0, out=None):
    if out is None: out = dict(actions=[], ings=[], states={}, comps=[], sources=[])
    out['sources'] += (d.get('recipe') or {}).get('sources') or []
    for c in d.get('components') or []:
        df = c.get('definition')
        if not df: continue
        info = dict(id=c['id'], name=s2t(df['recipe']['name']['zh_hant']), make_ahead=bool(c.get('make_ahead')),
                    parent=comp, depth=depth + 1, output=c['output_as'], shelf=c.get('shelf_life'))
        out['comps'].append(info)
        flatten(df, info, depth + 1, out)
    for i in d.get('ingredients') or []: out['ings'].append(dict(i, _comp=comp))
    for s in d.get('states') or []: out['states'][s['id']] = s
    for a in d.get('actions') or []: out['actions'].append(dict(a, _comp=comp))
    return out

def topo(actions):
    idx = {a['id']: n for n, a in enumerate(actions)}
    prod = {}
    for a in actions:
        for o in a.get('outputs') or []: prod[o] = a['id']
    deps = {a['id']: set() for a in actions}
    for a in actions:
        for x in (a.get('inputs') or []) + (a.get('requires_state') or []):
            if x in prod and prod[x] != a['id']: deps[a['id']].add(prod[x])
        for b in a.get('must_finish_before') or []:
            if b in deps: deps[b].add(a['id'])
    order, done = [], set()
    while len(order) < len(actions):
        ready = [a for a in actions if a['id'] not in done and deps[a['id']] <= done]
        if not ready: raise SystemExit('流程有迴圈')
        nxt = min(ready, key=lambda a: idx[a['id']])
        order.append(nxt); done.add(nxt['id'])
    return order, deps, prod

# ------------------------------------------------------------------ 換算
CONV = yaml.safe_load((SITE / 'conversions.yaml').read_text(encoding='utf-8'))
def conv_for(ing):
    q = ing['qty']
    if q.get('unit') != 'g' or q.get('value') is None: return None
    for it in CONV['items']:
        if ing['concept'] in it['concepts']:
            if it.get('only_labels') and not any(l in ing['label'] for l in it['only_labels']): return None
            return it
    return None

def conv_text(grams, it):
    if 'g_per_piece' in it:
        n = grams / it['g_per_piece']
        n = round(n * 2) / 2 if n < 20 else round(n)
        return f'約 {fmt_num(max(n, 0.5), "piece")} {it["piece"]}'
    tb = grams / it['g_per_tbsp']
    if tb >= 8:
        cup = round(tb / 16 * 4) / 4
        return f'約 {fmt_num(cup, "cup")} 杯（量杯）' if cup >= 0.25 else f'約 {fmt_num(round(tb*2)/2, "tbsp")} 大匙'
    if tb >= 1: return f'約 {fmt_num(round(tb * 2) / 2, "tbsp")} 大匙'
    tsp = tb * 3
    if tsp >= 0.25 - 1e-9: return f'約 {fmt_num(max(round(tsp * 4) / 4, 0.25), "tsp")} 小匙'
    return '不到 ¼ 小匙'

# ------------------------------------------------------------------ 一道菜的資料模型
def strip_paren(s):
    return re.sub(r'[（(][^）)]*[）)]', '', s).strip()

def build_model(path):
    d = yaml.safe_load(path.read_text(encoding='utf-8'))
    r = d['recipe']; rid = r['id']
    ov_path = SITE / 'content' / f'{rid}.yaml'
    ov = yaml.safe_load(ov_path.read_text(encoding='utf-8')) if ov_path.exists() else {}
    ov = ov or {}
    flat = flatten(d)
    # 來源編號（同 id 只留一筆）
    srcs, seen = [], set()
    for s in flat['sources']:
        if s['id'] in seen: continue
        seen.add(s['id']); srcs.append(s)
    srcmap = {s['id']: CIRCLED[n] for n, s in enumerate(srcs)}
    clean = make_cleaner(srcmap)
    order, deps, prod = topo(flat['actions'])
    num = {a['id']: n + 1 for n, a in enumerate(order)}
    ings = {i['id']: i for i in flat['ings']}
    comps = {c['id']: c for c in flat['comps']}
    return dict(d=d, r=r, rid=rid, ov=ov, flat=flat, srcs=srcs, srcmap=srcmap, clean=clean, order=order, deps=deps,
                prod=prod, num=num, ings=ings, comps=comps, name=s2t(r['name']['zh_hant']), slug=rid.split('.')[0])

def qty_html(ing, m):
    q = ing['qty']; v = q.get('value'); u = q.get('unit')
    if v is not None:
        uw = unit_word(u, ing['label'])
        note = '（義式原文的杯，原文沒定義容量）' if u == 'bicchiere' else '（義式原文的匙，原文沒定義容量）' if u == 'cucchiaio' else ''
        s = f'<span class="q" data-v="{v}" data-u="{u}" data-w="{E(uw)}">{fmt_num(v, u)} {E(uw)}</span>{note}'
        it = conv_for(ing)
        if it:
            s += (f'<span class="cv" data-g="{v}" data-k="{CONV["items"].index(it)}">換算值：{E(conv_text(v, it))}</span>')
        return s
    if q.get('qualitative'):
        return f'<span class="qual">{E(m["clean"](q["qualitative"]))}</span>'
    return '<span class="na">原文沒寫</span>'

def step_tool(a, m=None):
    t = a.get('tool') or ''
    if m and t in (m['ov'].get('tools') or {}): return m['ov']['tools'][t]
    return VZH.get(t, '')

def pot_name(a, m):
    return re.sub(r'（.*', '', step_tool(a, m))

def uses_burner(a):
    t = a.get('tool')
    if t not in BURNER_TOOLS: return False
    med = (VFACET.get(a.get('technique'), {}) or {}).get('medium')
    return med != 'none'

def lanes(m):
    """爐口分配：同一種鍋視為同一只鍋；只有標了『可同時』的步驟才會同時開火。"""
    order = m['order']
    over = {a['id']: set(a.get('can_overlap') or []) for a in order}
    for a in order:
        for b in list(over[a['id']]):
            if b in over: over[b].add(a['id'])
    pot = {a['id']: pot_name(a, m) for a in order if uses_burner(a)}
    co = {}
    for a, p in pot.items():
        for b in over[a]:
            if b in pot and pot[b] != p:
                co.setdefault(p, set()).add(pot[b]); co.setdefault(pot[b], set()).add(p)
    lane, first = {}, []
    for a in order:
        p = pot.get(a['id'])
        if p and p not in first: first.append(p)
    for p in first:
        used = {lane[q] for q in co.get(p, ()) if q in lane}
        lane[p] = next(n for n in range(1, 9) if n not in used)
    maxc = 0
    for a, p in pot.items():
        s = {p} | {pot[b] for b in over[a] if b in pot}
        maxc = max(maxc, len(s))
    if pot and maxc == 0: maxc = 1
    step_lane = {}
    for a in order:
        if a['id'] in pot: step_lane[a['id']] = ('burner', lane[pot[a['id']]], pot[a['id']])
        elif a.get('tool') == 'tool/electric_cooker': step_lane[a['id']] = ('cooker', 0, '電鍋')
        else: step_lane[a['id']] = ('none', 0, '')
    return step_lane, maxc, over

def lane_badge(l):
    kind, n, tool = l
    if kind == 'burner': return f'<span class="lane lane-b{n}">爐口 {n}・{E(tool)}</span>'
    if kind == 'cooker': return '<span class="lane lane-c">電鍋（不佔爐口）</span>'
    return '<span class="lane lane-n">不用開火</span>'

# ------------------------------------------------------------------ 流程圖
COLW, NODEW, NODEH, ROWH, TOP = 190, 168, 58, 100, 20
def trunc(s, n):
    return s if len(s) <= n else s[:n - 1] + '…'

def step_title(a, m):
    o = (m['ov'].get('steps') or {}).get(a['id']) or {}
    return o.get('title') or m['clean'](a['term'])

def flow_svg(m):
    order, deps, num = m['order'], m['deps'], m['num']
    ids = [a['id'] for a in order]; A = {a['id']: a for a in order}
    row, col, continued, ncol = {}, {}, set(), 0
    for a in order:
        i = a['id']
        row[i] = 1 + max([row[p] for p in deps[i]], default=-1)
        c = None
        for p in sorted(deps[i], key=lambda p: (-row[p], num[p])):
            if p not in continued: c = col[p]; continued.add(p); break
        if c is None: c = ncol; ncol += 1
        col[i] = c
    last = order[-1]['id']
    fin_row = row[last] + 1
    W = ncol * COLW + 20
    H = TOP + (fin_row + 1) * ROWH + 10
    X = lambda c: 10 + c * COLW + COLW / 2
    Y = lambda r: TOP + 26 + r * ROWH
    o = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="flow-t" xmlns="http://www.w3.org/2000/svg" style="--fw:{W}">',
         f'<title id="flow-t">{E(m["name"])}流程圖：由上往下，每個方塊是一個步驟，線表示做好的東西交給下一步</title>',
         '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="fl-ah"/></marker></defs>']
    # 子食譜框
    for c in m['flat']['comps']:
        mem = [i for i in ids if A[i]['_comp'] and (A[i]['_comp']['id'] == c['id'] or (A[i]['_comp'].get('parent') or {}).get('id') == c['id'])]
        if not mem or c['depth'] > 1: continue  # 只畫最外層的醬料框，內層框會和外層標題疊在一起
        c0, c1 = min(col[i] for i in mem), max(col[i] for i in mem)
        r0, r1 = min(row[i] for i in mem), max(row[i] for i in mem)
        inside = [i for i in ids if c0 <= col[i] <= c1 and r0 <= row[i] <= r1 and i not in mem]
        if inside: continue
        pad = 8 + 6 * (2 - min(c['depth'], 2))
        x = 10 + c0 * COLW + pad - 4; y = Y(r0) - 30 - (2 - min(c['depth'], 2)) * 4
        w = (c1 - c0 + 1) * COLW - 2 * pad + 8; h = Y(r1) + NODEH + 12 - y
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" class="fl-group"/>')
        o.append(f'<text x="{x + 10}" y="{y + 18}" class="fl-glabel">{E(trunc("醬料或配料：" + c["name"] if c["depth"] == 1 else c["name"], int(w / 13)))}</text>')
    # 線
    def edge(x1, y1, x2, y2, chan):
        if abs(x1 - x2) < 1 and chan is None: return f'M{x1},{y1} V{y2 - 2}'
        if chan is None: return f'M{x1},{y1} V{y2 - 16} H{x2} V{y2 - 2}'
        return f'M{x1},{y1} V{y1 + 12} H{chan} V{y2 - 16} H{x2} V{y2 - 2}'
    for i in ids:
        ps = sorted(deps[i], key=lambda p: (col[p], num[p]))
        for k, p in enumerate(ps):
            x1, y1 = X(col[p]), Y(row[p]) + NODEH
            dx = 0 if len(ps) == 1 else (-30 + 60 * k / (len(ps) - 1))
            x2, y2 = X(col[i]) + dx, Y(row[i])
            between = [j for j in ids if j not in (p, i) and row[p] < row[j] < row[i] and (col[j] == col[p] or col[j] == col[i])]
            if col[p] == col[i] and not between: d = edge(x1, y1, x2, y2, None)
            elif row[i] == row[p] + 1 and not between: d = edge(x1, y1, x2, y2, None)
            else:
                side = 1 if col[i] >= col[p] else -1
                chan = X(col[p]) + side * COLW / 2
                d = edge(x1, y1, x2, y2, chan)
            cls = 'fl-edge is-sub' if A[p]['_comp'] else 'fl-edge'
            o.append(f'<path d="{d}" class="{cls}" marker-end="url(#ah)"/>')
    # 方塊
    for i in ids:
        a = A[i]; x = X(col[i]) - NODEW / 2; y = Y(row[i])
        t = step_title(a, m)
        l1 = t if len(t) <= 7 else ((m['ov'].get('steps') or {}).get(i) or {}).get('flow') or VZH.get(a['technique'], trunc(t, 7))
        names = [strip_paren(s2t(m['ings'][x_]['label'])) for x_ in a.get('inputs') or [] if x_ in m['ings']]
        l2 = '、'.join(names) if names else step_tool(a, m)
        kind = 'fl-sub' if a['_comp'] else 'fl-step'
        o.append(f'<a href="#s{num[i]}" class="fl-link"><g class="fl-node {kind}"><rect x="{x}" y="{y}" width="{NODEW}" height="{NODEH}" rx="12"/>'
                 f'<circle cx="{x + 18}" cy="{y + 20}" r="13" class="fl-num"/><text x="{x + 18}" y="{y + 25}" text-anchor="middle" class="fl-numt">{num[i]}</text>'
                 f'<text x="{x + 38}" y="{y + 26}" class="fl-t1">{E(trunc(l1, 8))}</text>'
                 f'<text x="{x + 12}" y="{y + 48}" class="fl-t2">{E(trunc(l2, 11))}</text></g></a>')
    fx, fy = max(X(col[last]), 100), Y(fin_row)
    o.append(f'<path d="M{X(col[last])},{Y(row[last]) + NODEH} V{fy - 16} H{fx} V{fy - 2}" class="fl-edge" marker-end="url(#ah)"/>')
    o.append(f'<g class="fl-node fl-final"><rect x="{fx - 90}" y="{fy}" width="180" height="{NODEH}" rx="12"/>'
             f'<text x="{fx}" y="{fy + 35}" text-anchor="middle" class="fl-t1">{E(trunc("完成：" + m["name"], 12))}</text></g>')
    o.append('</svg>')
    return '\n'.join(o), W

# ------------------------------------------------------------------ 步驟
NO_THERMO = '家裡沒有溫度計：原文沒寫不用溫度計怎麼判斷，請先看「好了的樣子」，試做後再補上。'
def fact(label, val, cls=''):
    if not val: return f'<div class="fact {cls}"><dt>{label}</dt><dd><span class="na">原文沒寫</span></dd></div>'
    if cls != 'fact-done' and re.search(r'沒寫|未寫|未註明|未給', val) and len(val) < 40: return f'<div class="fact {cls}"><dt>{label}</dt><dd><span class="na">{val}</span></dd></div>'
    return f'<div class="fact {cls}"><dt>{label}</dt><dd>{val}</dd></div>'

DROPPED = []
def zh_only(s, m, where):
    """原文是外文時，改用括號裡的中文說明；沒有中文說明就記下來，要在白話說明檔補。"""
    if not s: return None
    t = m['clean'](s)
    if t and not re.search(r'[A-Za-z]{3,}', t): return t
    zh = re.findall(r'[（(]([^（）()]*)[）)]', s2t(str(s)))
    zh = [z for z in zh if z and not re.search(r'[A-Za-z]{3,}', z)]
    if zh: return '原文：' + '；'.join(zh)
    DROPPED.append(f'{m["rid"]} {where}: {s}')
    return None

def raw_or_none(s, m, where=''):
    t = zh_only(s, m, where)
    return E(t) if t else None

def state_label(x, m):
    if x in (m['ov'].get('states') or {}): return m['ov']['states'][x]
    st = m['flat']['states'].get(x) or {}
    if st.get('label'): return m['clean'](st['label'])
    for c in m['flat']['comps']:
        if c['output'] == x: return c['name']
    return step_title({a['id']: a for a in m['order']}[m['prod'][x]], m)

def is_heat_step(a):
    return uses_burner(a) or a.get('tool') == 'tool/electric_cooker'

def steps_html(m, step_lane, over):
    out = []; num = m['num']; ovs = m['ov'].get('steps') or {}
    for a in m['order']:
        i = a['id']; n = num[i]; o = ovs.get(i) or {}; p = a.get('params') or {}
        title = step_title(a, m)
        # 放進去的東西
        ins = []
        for x in a.get('inputs') or []:
            if x in m['ings']:
                ing = m['ings'][x]
                ins.append(f'<li><span class="ing-name">{E(m['clean'](ing["label"]))}</span><span class="ing-qty">{qty_html(ing, m)}</span></li>')
            elif x in m['prod']:
                ins.append(f'<li><span class="ing-name">第 {num[m["prod"][x]]} 步做好的{E(state_label(x, m))}</span><span class="ing-qty"></span></li>')
        heat = o.get('heat') or raw_or_none((p.get('heat') or {}).get('raw'), m, i + ' 火候') or (VZH.get((p.get('heat') or {}).get('level') or '', None))
        dur = o.get('time') or raw_or_none((p.get('duration') or {}).get('raw'), m, i + ' 時間')
        temp = None
        tp = p.get('temperature')
        if tp:
            temp = o.get('temp') or zh_only(tp.get('raw'), m, i + ' 溫度') or ''
            if tp.get('min_c') is not None or tp.get('max_c') is not None: temp = (temp + '。' if temp else '') + NO_THERMO
        done = o.get('done')
        if done is None:
            done = []
            if o.get('done_extra'): pass
            for c in a.get('completion') or []:
                t = zh_only(c.get('target'), m, i + ' 好了的樣子')
                if t: done.append(f'{m["clean"](c["observe"])}：{t}')
        done = list(done) + list(o.get('done_extra') or [])
        done_html = '<ul class="done-list">' + ''.join(f'<li>{E(x)}</li>' for x in done) + '</ul>' if done else None
        tips = []
        for k in ('risk', 'constraint', 'control'):
            if a.get(k) and not o.get('hide_' + k):
                t = zh_only(a[k], m, i + ' ' + k)
                if t: tips.append(t)
        ob = a.get('optional_branch')
        if ob and not o.get('hide_branch'):
            tips.append(f'可以選擇做（{m["clean"](ob.get("at", ""))}）：{m["clean"](ob.get("action", ""))}')
        tips += o.get('tips') or []
        ov_ = sorted(num[b] for b in over.get(i, ()) if b in num)
        par = f'<span class="badge badge-par">可和第 {"、".join(map(str, ov_))} 步同時做</span>' if ov_ else ''
        sub = f'<span class="badge badge-sub">{E(a["_comp"]["name"])}</span>' if a['_comp'] else ''
        tool = step_tool(a, m)
        out.append(f'''<li class="step{' step-sub' if a['_comp'] else ''}" id="s{n}">
  <label class="step-check"><input type="checkbox" data-step="{n}"><span class="box" aria-hidden="true"></span><span class="zd-visually-hidden">完成第 {n} 步</span></label>
  <div class="step-body">
    <h3 class="step-h"><span class="step-no">{n}</span><span>{E(title)}</span></h3>
    <p class="step-badges">{lane_badge(step_lane[i])}{sub}{par}</p>
    {('<ul class="ing-list step-ins">' + ''.join(ins) + '</ul>') if ins else ''}
    <dl class="facts">{fact('用什麼', E(tool)) if tool else ''}{fact('火候', heat) if (heat or is_heat_step(a)) else ''}{fact('時間', dur) if (dur or is_heat_step(a) or p.get('duration')) else ''}{fact('溫度', E(temp)) if temp else ''}{fact('好了的樣子', done_html, 'fact-done')}</dl>
    {''.join(f'<p class="tip">{E(t)}</p>' for t in tips)}
  </div>
</li>''')
    return '\n'.join(out)

# ------------------------------------------------------------------ 時間安排
def timeline_html(m, step_lane, maxc, over):
    order, num, deps = m['order'], m['num'], m['deps']
    anc_burner = {}
    for a in order:
        anc_burner[a['id']] = uses_burner(a) or a.get('tool') == 'tool/electric_cooker' or any(anc_burner[p] for p in deps[a['id']])
    def ahead(a):
        c = a['_comp']
        while c:
            if c['make_ahead']: return c
            c = c.get('parent')
        return None
    prep, early, fire = [], {}, []
    for a in order:
        c = ahead(a)
        if c: early.setdefault(c['name'], []).append(a)
        elif not anc_burner[a['id']]: prep.append(a)
        else: fire.append(a)
    def chip(a):
        return f'<li class="tl-chip{" is-sub" if a["_comp"] else ""}"><a href="#s{num[a["id"]]}">{num[a["id"]]} {E(trunc(step_title(a, m), 14))}</a>{lane_badge(step_lane[a["id"]])}</li>'
    ph = []
    if early:
        for name, acts in early.items():
            ph.append(('可以先做好', f'{name}：前一天或開火前做好放著', ''.join(chip(a) for a in acts)))
    if prep: ph.append(('先備好', '不用開火，順序不拘，可以先做', ''.join(chip(a) for a in prep)))
    if fire: ph.append(('開火做', '照順序做；標「可同時」的才一起做', ''.join(chip(a) for a in fire)))
    body = ''.join(f'<li class="tl-phase"><div class="tl-h"><span class="tl-name">{E(a)}</span><span class="tl-sub">{E(b)}</span></div><ul class="tl-chips">{c}</ul></li>' for a, b, c in ph)
    burn = m['ov'].get('burners')
    cooker = any(v[0] == 'cooker' for v in step_lane.values())
    summ = f'這道菜同時最多用 <b>{maxc} 口爐</b>' + ('，電鍋不佔爐口' if cooker else '') + '。' if maxc else '這道菜不用開瓦斯爐。'
    return f'<p class="burner-sum">{summ}{(" " + E(burn)) if burn else ""}</p><ol class="timeline">{body}</ol>'

# ------------------------------------------------------------------ 材料與購物清單
SKIP_SHOP = {'ing/water', 'ing/pan_fond'}
SEASON_ROLES = {'調料', '香料', '油脂', '芡粉', '液體'}
def ing_li(ing, m):
    opt = '（可省）' if ing.get('optional') else ''
    buy = '（買現成的）' if ing.get('product') and '市售' not in ing['label'] and '購買' not in ing['label'] else ''
    note = ((m['ov'].get('ing') or {}).get(ing['id']) or {}).get('note')
    nt = f'<span class="ing-note">{E(note)}</span>' if note else ''
    return f'<li><span class="ing-name">{E(m['clean'](ing["label"]))}{opt}{buy}{nt}</span><span class="ing-qty">{qty_html(ing, m)}</span></li>'

def ingredients_html(m):
    main = [i for i in m['flat']['ings'] if i['_comp'] is None]
    cards = [f'<div class="card ing-col"><h3 class="ing-h">主菜</h3><ul class="ing-list">{"".join(ing_li(i, m) for i in main)}</ul></div>']
    for c in m['flat']['comps']:
        its = [i for i in m['flat']['ings'] if i['_comp'] and i['_comp']['id'] == c['id']]
        if not its: continue
        tag = '可以先做' if c['make_ahead'] else '做菜時一起做'
        parent = f'（{c["parent"]["name"]}裡的一部分）' if c.get('parent') else ''
        cards.append(f'<div class="card ing-col sub-card"><h3 class="ing-h"><span class="sub-dot" aria-hidden="true"></span>{E(c["name"])}</h3>'
                     f'<p class="sub-tag">{tag}{E(parent)}</p><ul class="ing-list">{"".join(ing_li(i, m) for i in its)}</ul></div>')
    return '<div class="ing-grid">' + ''.join(cards) + '</div>'

def shopping_html(m):
    groups = {'生鮮與主料': {}, '調味料與乾貨': {}}
    for i in m['flat']['ings']:
        con = i['concept'] if isinstance(i['concept'], str) else '+'.join(i['concept'])
        if con in SKIP_SHOP: continue
        g = '調味料與乾貨' if i['role'] in SEASON_ROLES else '生鮮與主料'
        name = VZH.get(con) or strip_paren(s2t(i['label']))
        if '辣椒油' in i['label']: name = '辣椒油（市售）'
        q = i['qty']; key = (name, q.get('unit') if q.get('value') is not None else None)
        e = groups[g].setdefault(key, dict(name=name, v=0.0, u=q.get('unit'), has=False, qual=[], miss=False, opt=True, label=s2t(i['label'])))
        e['opt'] = e['opt'] and bool(i.get('optional'))
        if q.get('value') is not None: e['v'] += q['value']; e['has'] = True
        elif q.get('qualitative'): e['qual'].append(m['clean'](q['qualitative']))
        else: e['miss'] = True
    out = []
    for g, items in groups.items():
        if not items: continue
        lis = []
        for e in items.values():
            if e['has']:
                uw = unit_word(e['u'], e['label'])
                qty = f'<span class="q" data-v="{round(e["v"], 4)}" data-u="{e["u"]}" data-w="{E(uw)}">{fmt_num(e["v"], e["u"])} {E(uw)}</span>'
            elif e['qual']: qty = E('、'.join(dict.fromkeys(e['qual'])))
            else: qty = '<span class="na">份量原文沒寫</span>'
            opt = '（可省）' if e['opt'] else ''
            lis.append(f'<li><label><input type="checkbox"><span>{E(e["name"])}{opt}</span></label><span class="ing-qty">{qty}</span></li>')
        out.append(f'<div class="shop-g"><h3 class="ing-h">{g}</h3><ul class="shop-list">{"".join(lis)}</ul></div>')
    return ('<div class="card shop">' + ''.join(out) +
            '<div class="shop-actions"><button type="button" class="zd-btn zd-btn--secondary copy-shop">複製清單</button><span class="shop-msg" role="status" aria-live="polite"></span></div>'
            '<p class="zd-small">同一樣材料在不同步驟用到的量已經加總；份數按鈕也會一起換算。肉、魚請攤商或看包裝上的重量，家裡不用秤。</p></div>')

# ------------------------------------------------------------------ 辣與麻
def spice_html(m):
    sp = m['ov'].get('spice') or {}
    mode = sp.get('mode', 'none')
    head = {'addon': '一鍋兩吃，最後分開加', 'separate': '要分開做', 'none': '本來就不辣不麻'}[mode]
    cls = {'addon': 'ok', 'separate': 'off', 'none': 'na'}[mode]
    cols = ''
    if sp.get('wife') or sp.get('yours'):
        cols = (f'<div class="vs"><div class="vs-a"><p class="vs-h">太太那份：不辣不麻</p><ul>{"".join(f"<li>{E(x)}</li>" for x in sp.get("wife") or [])}</ul></div>'
                f'<div class="vs-b"><p class="vs-h">你那份：微辣、微麻</p><ul>{"".join(f"<li>{E(x)}</li>" for x in sp.get("yours") or [])}</ul></div></div>')
    return (f'<section class="block" aria-labelledby="spice-h"><div class="card spice spice-{cls}"><h2 class="h2" id="spice-h">辣與麻：{head}</h2>'
            f'<p>{E(sp.get("text", ""))}</p>{cols}</div></section>')

# ------------------------------------------------------------------ 頁面
def head(title, depth=''):
    a = f'{depth}assets/{ASSET_VER}'
    return f'''<!doctype html>
<html lang="zh-Hant-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{E(title)}</title>
<link rel="icon" href="{a}/icons/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{a}/icons/apple-touch-icon.png">
<link rel="stylesheet" href="{a}/fonts/fonts.css">
<link rel="stylesheet" href="{a}/tokens.css">
<link rel="stylesheet" href="{a}/components.css">
<link rel="stylesheet" href="{depth}assets/site.css">
</head>
<body class="zd">'''

def topbar(depth='', back=True):
    nav = f'<a class="top-back" href="{depth}index.html">← 全部菜色</a>' if back else ''
    return f'<header class="top"><div class="top-in"><a class="brand" href="{depth}index.html">振達的廚房</a>{nav}<a class="top-conv" href="{depth}conversions.html">換算表</a></div></header>'

FOOT = '<footer class="zd-footer">振達的廚房・食譜 v1｜數字只用原始食譜寫的，原文沒寫的就標「原文沒寫」｜振達設計規範 Workshop 1.2.1</footer>'

def feedback_btn(name, where):
    return (f'<div class="fb-row-btn"><a class="zd-btn zd-btn--primary fb-btn" href="{NOTION_URL}" target="_blank" rel="noopener noreferrer" data-where="{where}">我做了這道</a>'
            f'<span class="zd-small">打開你的 Notion 做菜紀錄，記下「{E(name)}」做得怎麼樣（只在 Notion 裡，不會放到這個網站）。</span></div>')

def tag_badge(tag):
    t, cls, shape = TAGS[tag]
    return f'<span class="zd-signal zd-signal--{cls} tag">{t}</span>'

def serving_html(m):
    sv = m['d'].get('serving') or {}
    ovs = m['ov'].get('serving')
    lis = []
    if ovs is not None: lis = list(ovs)
    else:
        for c in sv.get('completion') or []:
            t = m['clean'](c.get('target'))
            if t and not re.search(r'[A-Za-z]{3,}', t):
                lis.append(f'{m["clean"](c["observe"])}：{t}' + ('（家裡沒有溫度計，參考就好）' if '°C' in t else ''))
    st = sv.get('sensory_target') or {}
    for k, lab in (('color', '顏色'), ('taste', '味道'), ('texture', '口感')):
        if st.get(k):
            t = m['clean'](st[k])
            if not re.search(r'[A-Za-z]{3,}', t): lis.append(f'{lab}：{t}')
    if not lis: return ''
    return f'<section class="block" aria-labelledby="sv-h"><h2 class="h2" id="sv-h">上桌：成品該有的樣子</h2><ul class="card plain-list">{"".join(f"<li>{E(x)}</li>" for x in lis)}</ul></section>'

def sources_html(m):
    lis = []
    for s in m['srcs']:
        lv = LEVEL.get(s['level'], '')
        lis.append(f'<li><span class="src-no">{m["srcmap"][s["id"]]}</span><span class="src-lv">{lv}</span>'
                   f'<a href="{E(s["url"])}" target="_blank" rel="noopener noreferrer">{E(s2t(s["title"]))}</a></li>')
    return '<ol class="src-list">' + ''.join(lis) + '</ol>'

def notes_html(m):
    ov = m['ov']; parts = []
    if ov.get('missing'):
        parts.append('<div class="note-block"><h3 class="h3">原文沒寫、這頁也不亂補的地方</h3><ul>' + ''.join(f'<li>{E(x)}</li>' for x in ov['missing']) + '</ul></div>')
    if ov.get('notes'):
        parts.append('<div class="note-block"><h3 class="h3">做之前先知道</h3><ul>' + ''.join(f'<li>{E(x)}</li>' for x in ov['notes']) + '</ul></div>')
    if ov.get('compare'):
        parts.append('<div class="note-block"><h3 class="h3">和其他版本的差別</h3><ul>' + ''.join(f'<li>{E(x)}</li>' for x in ov['compare']) + '</ul></div>')
    return ''.join(parts)

def servings_text(m):
    sv = m['r'].get('servings') or {}
    if sv.get('value'): return f'{fmt_num(sv["value"], "piece")} 人份'
    return '原文沒寫幾人份'

def recipe_page(m):
    ov = m['ov']; r = m['r']
    step_lane, maxc, over = lanes(m)
    svg, W = flow_svg(m)
    cuis = '・'.join(dict.fromkeys(VZH.get(c['id'], '') for c in r.get('cuisine') or [] if VZH.get(c['id'])))
    levels = '、'.join(dict.fromkeys(LEVEL[s['level']] for s in m['srcs']))
    intro = ov.get('intro') or m['clean'](r.get('summary') or '')
    variant = ov.get('variant') or (m['clean'](r.get('variant')) if r.get('variant') else '')
    spm = (ov.get('spice') or {}).get('mode', 'none')
    meta = [('份量', servings_text(m)), ('什麼時候做', TAGS[ov['tag']][0]), ('數字依據', levels),
            ('辣與麻', {'addon': '一鍋兩吃，最後分開加', 'separate': '要分開做', 'none': '不辣不麻'}[spm])]
    nsteps = len(m['order'])
    body = f'''{topbar('../')}
<main class="wrap">
<header class="hero card">
  <p class="zd-kicker">{E(cuis)}</p>
  <h1 class="dish-name">{E(m['name'])}</h1>
  <p class="tagline">{tag_badge(ov['tag'])}{f'<span class="variant">{E(variant)}</span>' if variant else ''}</p>
  <p class="intro">{E(intro)}</p>
  {f'<p class="zd-small tag-note">{E(ov["tag_note"])}</p>' if ov.get('tag_note') else ''}
  {'<p class="check-note">這道菜的數字已經對過原文，但還沒做第二輪「兩邊交叉比對」。照著做沒問題，數字以後可能會小修。</p>' if r.get('status') == 'machine_checked' else ''}
  <ul class="meta">{''.join(f'<li><span class="meta-k">{k}</span><span class="meta-v">{E(v)}</span></li>' for k, v in meta)}</ul>
  {feedback_btn(m['name'], 'top')}
  <nav class="jump" aria-label="跳到">{''.join(f'<a href="#{a}">{b}</a>' for a, b in (('ing-h','材料'),('shop-h','購物清單'),('flow-h','流程圖'),('tl-h','時間安排'),('steps-h','步驟'),('src-h','來源')))}</nav>
</header>
{spice_html(m)}
<section class="block" aria-labelledby="ing-h"><h2 class="h2" id="ing-h">準備材料</h2>
  <div class="scale" role="group" aria-label="份量倍數"><span class="scale-k">份量</span>{''.join(f'<button type="button" class="scale-btn" data-s="{s}" aria-pressed="{"true" if s == 1 else "false"}">{lab}</button>' for s, lab in ((0.5, '半份'), (1, '原份量'), (1.5, '1.5 倍'), (2, '2 倍')))}</div>
  <p class="zd-small scale-note">按倍數只會換算材料份量；火候、時間和「好了的樣子」不跟著變，份量變大時鍋子也要夠大。「換算值」是用公開換算表算出的湯匙或目測數，只是方便你不用秤，<a href="../conversions.html">看換算表和出處</a>。</p>
  {ingredients_html(m)}
</section>
<section class="block" aria-labelledby="shop-h"><h2 class="h2" id="shop-h">購物清單</h2>{shopping_html(m)}</section>
<section class="block" aria-labelledby="flow-h"><h2 class="h2" id="flow-h">流程圖：材料怎麼變成一道菜</h2>
  <p class="lead">由上往下看。每個方塊是一個步驟（點方塊可以跳到那一步），線表示做好的東西交給下一步。<span class="legend"><span class="lg lg-step">主菜步驟</span><span class="lg lg-sub">醬料或配料（子食譜）</span></span></p>
  <figure class="card flow"><p class="flow-hint">← 左右滑動看完整流程圖 →</p><div class="flow-scroll" style="--flow-min:{int(W)}px">{svg}</div></figure>
</section>
<section class="block" aria-labelledby="tl-h"><h2 class="h2" id="tl-h">時間安排：什麼先做、用哪口爐</h2>{timeline_html(m, step_lane, maxc, over)}</section>
<section class="block" aria-labelledby="steps-h"><h2 class="h2" id="steps-h">一步一步做</h2>
  <div class="steps-bar"><span class="progress">已完成 0 / {nsteps}</span><button type="button" class="zd-btn zd-btn--quiet reset">清除勾選</button></div>
  <p class="honest">這頁的數字都來自下面的來源。原文沒寫的火候、時間，就寫「原文沒寫」，請照「好了的樣子」判斷。</p>
  <ol class="steps">{steps_html(m, step_lane, over)}</ol>
</section>
{serving_html(m)}
<section class="block" aria-labelledby="nt-h"><h2 class="h2" id="nt-h">備註</h2><div class="card notes">{notes_html(m) or '<p>沒有其他備註。</p>'}</div></section>
<section class="block" aria-labelledby="src-h"><h2 class="h2" id="src-h">來源</h2><div class="card notes">{sources_html(m)}<p class="zd-small">步驟裡寫「來源①」之類的，就是指這裡的編號。</p></div></section>
<section class="block fb-end">{feedback_btn(m['name'], 'bottom')}</section>
</main>
{FOOT}
<script>window.ZD_CONV={json.dumps([[it.get('g_per_tbsp'), it.get('g_per_piece'), it.get('piece')] for it in CONV['items']], ensure_ascii=False)};window.ZD_KEY={json.dumps(m['slug'])};</script>
<script src="../assets/site.js"></script>
</body></html>'''
    return head(f'{m["name"]}｜振達的廚房', '../') + body

def index_page(models):
    cards = []
    for m in models:
        ov = m['ov']; spm = (ov.get('spice') or {}).get('mode', 'none')
        cuis = '・'.join(dict.fromkeys(VZH.get(c['id'], '') for c in m['r'].get('cuisine') or [] if VZH.get(c['id'])))
        cards.append(f'''<li class="dish-card card" data-tag="{ov['tag']}"><a href="recipes/{m['slug']}.html">
<p class="zd-kicker">{E(cuis)}</p><h2 class="h2 dc-name">{E(m['name'])}</h2>
<p class="dc-tag">{tag_badge(ov['tag'])}</p>
<p class="dc-intro">{E(ov.get('card') or m['clean'](m['r'].get('summary') or ''))}</p>
<p class="zd-small dc-meta">{'還沒做第二輪比對・' if m['r'].get('status') == 'machine_checked' else ''}{E(servings_text(m))}・{len(m['order'])} 個步驟・{ {'addon': '辣麻最後分開加', 'separate': '辣的要分開做', 'none': '不辣不麻'}[spm] }</p></a></li>''')
    counts = {k: sum(1 for m in models if m['ov']['tag'] == k) for k in TAGS}
    chips = f'<button type="button" class="zd-chip filt" data-f="all" aria-pressed="true">全部 {len(models)}</button>' + ''.join(
        f'<button type="button" class="zd-chip filt" data-f="{k}" aria-pressed="false">{TAGS[k][0]} {counts[k]}</button>' for k in TAGS)
    body = f'''{topbar('', back=False)}
<main class="wrap">
<header class="hero card home-hero">
  <p class="zd-kicker">食譜 v1・{len(models)} 道</p>
  <h1 class="dish-name">今天做哪一道？</h1>
  <p class="intro">每道菜都有材料、購物清單、流程圖、用爐安排和一步一步的做法。數字只用原始食譜寫的；原文沒寫的地方會直接標「原文沒寫」，請照「好了的樣子」判斷。</p>
  <ul class="how">
    <li><b>平日可做</b>：依原文時間 20 分鐘內。</li><li><b>假日菜</b>：原文時間明顯超過 20 分鐘。</li><li><b>待試做計時</b>：原文沒寫總時間，要你做一次計時才知道。</li>
  </ul>
</header>
<div class="filters" role="group" aria-label="篩選">{chips}</div>
<ul class="dish-grid">{''.join(cards)}</ul>
<p class="zd-small">做完一道，在那道菜的頁面按「我做了這道」，就會打開你的 Notion 做菜紀錄。</p>
</main>
{FOOT}
<script src="assets/site.js"></script>
</body></html>'''
    return head('振達的廚房・食譜', '') + body

def conversions_page():
    rows = []
    for it in CONV['items']:
        if 'g_per_tbsp' in it:
            val = f'1 大匙 ≈ {fmt_num(it["g_per_tbsp"], "g")} 克'
        else:
            val = f'1 {it["piece"]} ≈ {it["g_per_piece"]} 克'
        rows.append(f'<tr><td>{E(it["name"])}</td><td>{E(val)}</td><td><a href="https://fdc.nal.usda.gov/food-details/{it["fdc"]}/nutrients" target="_blank" rel="noopener noreferrer">美國農業部資料第 {it["fdc"]} 號</a></td></tr>')
    s = CONV['sources']
    body = f'''{topbar('')}
<main class="wrap">
<header class="hero card"><p class="zd-kicker">換算值怎麼來的</p><h1 class="dish-name">湯匙與目測換算表</h1>
<p class="intro">家裡沒有秤，所以食譜頁會在克數旁邊加一行「換算值」，告訴你大約幾大匙、幾瓣、幾片。這些換算值只用下面兩個公開出處算出來，<b>不會寫回食譜</b>；食譜本身的數字還是以原文的克數為準。</p></header>
<section class="block"><h2 class="h2">換算規則</h2><ul class="card plain-list">
<li>1 大匙＝3 小匙＝15 毫升；1 杯（量杯）＝16 大匙＝240 毫升（出處②）。</li>
<li>每樣材料 1 大匙或 1 個有多重，用出處①的「常用份量」重量。</li>
<li>大匙四捨五入到半匙、小匙到 ¼ 匙，所以寫「約」。超過 4 大匙改用量杯。</li>
<li>只換算查得到可靠對應的材料。花椒、郫縣豆瓣、豆豉、醬油膏、冰糖、紅糖、水澱粉、味精這些查不到可靠數字，就不換算。</li>
<li>出處①是美國的食材，和台灣買到的可能有點差別（例如醬油、米酒的濃淡），所以換算值只是大約，味道以你試吃為準。</li>
</ul></section>
<section class="block"><h2 class="h2">每樣材料的換算</h2><div class="zd-table-wrap card"><table class="zd-table"><thead><tr><th>材料</th><th>換算</th><th>出處①的資料</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section class="block"><h2 class="h2">出處</h2><ol class="card src-list">
<li><span class="src-no">①</span><a href="{E(s['usda']['url'])}" target="_blank" rel="noopener noreferrer">{E(s['usda']['title'])}</a></li>
<li><span class="src-no">②</span><a href="{E(s['nist']['url'])}" target="_blank" rel="noopener noreferrer">{E(s['nist']['title'])}</a></li></ol></section>
</main>
{FOOT}
</body></html>'''
    return head('湯匙與目測換算表｜振達的廚房', '') + body

# ------------------------------------------------------------------ 檢查：白話、不補數字
VISIBLE_SKIP = re.compile(r'<(script|style)[^>]*>.*?</\1>|<ol class="(?:card )?src-list">.*?</ol>|<title[^>]*>.*?</title>', re.S)
ALLOWED_LATIN = {'Notion', 'Workshop', 'AA'}
BANNED = ['yaml', 'status', 'sourced', 'inferred', 'missing', 'cross_checked', 'tech/', 'tool/', 'ing/', 'schema', '詞表', '規格', 'Kimi', 'Codex', 'notes', 'research/']
def visible_text(page):
    t = VISIBLE_SKIP.sub(' ', page)
    t = re.sub(r'<[^>]+>', ' ', t)
    return html.unescape(t)

def lint(pages):
    problems = []
    for name, page in pages.items():
        t = visible_text(page)
        for w in sorted(set(re.findall(r'[A-Za-z][A-Za-z_./-]{1,}', t))):
            if w not in ALLOWED_LATIN: problems.append(f'{name}: 英文字「{w}」')
        for b in BANNED:
            if b.lower() in t.lower(): problems.append(f'{name}: 技術詞「{b}」')
        if 'name="robots" content="noindex,nofollow"' not in page: problems.append(f'{name}: 缺 noindex')
    return problems

NUM = re.compile(r'\d+(?:\.\d+)?')
def number_guard(m):
    """白話說明檔（site/content）裡出現的每個數字，都必須在原食譜檔裡找得到。"""
    p = SITE / 'content' / f'{m["rid"]}.yaml'
    if not p.exists(): return []
    src = (ROOT / 'recipes').glob(f'{m["rid"]}.yaml')
    raw = s2t(next(src).read_text(encoding='utf-8'))
    src_nums = set(NUM.findall(raw))
    bad = []
    for n in NUM.findall(p.read_text(encoding='utf-8')):
        if n not in src_nums and n not in ('1', '2'):  # 「1 口爐、2 口爐」「第 1 步」這類計數另由步驟號檢查
            bad.append(n)
    return [f'{p.name}: 數字 {n} 在原食譜檔找不到' for n in sorted(set(bad))]

# ------------------------------------------------------------------ 字型
def build_fonts(text, dest):
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    from fontTools import subset
    ds = Path('/workspace/design-system')
    chars = set(text) | set(' 0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,:;!?()%°～—–-+/\'"←→↓✓●○◐◆▲①②③④⑤⑥⑦⑧⑨⑩¼½¾⅓⅔⅙⅚…・「」『』（）、，。：；！？')
    faces = ['/* 字型：Noto Sans TC、Figtree（SIL Open Font License 1.1），只收本站用到的字；由 site/build_site.py --fonts 產生 */']
    for w in (400, 700):
        f = TTFont(str(ds / 'fonts/src/NotoSansTC[wght].ttf'))
        f = instancer.instantiateVariableFont(f, {'wght': w})
        opts = subset.Options(); opts.flavor = 'woff2'; opts.layout_features = ['*']
        sub = subset.Subsetter(opts); sub.populate(text=''.join(sorted(chars))); sub.subset(f)
        f.flavor = 'woff2'; f.save(str(dest / f'noto-sans-tc-{w}-site.woff2'))
        faces.append(f'@font-face{{font-family:"Noto Sans TC";font-style:normal;font-weight:{w};font-display:swap;src:url("noto-sans-tc-{w}-site.woff2") format("woff2")}}')
    shutil.copy(ds / 'fonts/figtree-var-latin.woff2', dest / 'figtree-var-latin.woff2')
    faces.append('@font-face{font-family:"Figtree";font-style:normal;font-weight:300 900;font-display:swap;src:url("figtree-var-latin.woff2") format("woff2");unicode-range:U+0000-00FF,U+2000-206F,U+2190-2193,U+2212}')
    (dest / 'fonts.css').write_text('\n'.join(faces) + '\n', encoding='utf-8')

# ------------------------------------------------------------------ 主程式
def main():
    order_pref = yaml.safe_load((SITE / 'order.yaml').read_text(encoding='utf-8')) or []
    paths = [p for p in sorted((ROOT / 'recipes').glob('*.yaml')) if p.name.split('.')[0] in order_pref]
    skipped = [p.name for p in sorted((ROOT / 'recipes').glob('*.yaml')) if p.name.split('.')[0] not in order_pref]
    if skipped: print('不在網站清單、這次不上網站：', '、'.join(skipped))
    models = [build_model(p) for p in paths]
    notready = [m['rid'] for m in models if m['r'].get('status') not in ('machine_checked', 'cross_checked', 'spot_checked', 'tried', 'gold')]
    if notready: raise SystemExit(f'還沒兩邊比對過，不能上網站：{notready}')
    models.sort(key=lambda m: (order_pref.index(m['slug']) if m['slug'] in order_pref else 99, m['slug']))
    missing_ov = [m['rid'] for m in models if not m['ov'].get('tag')]
    if missing_ov: raise SystemExit(f'缺白話說明檔或 tag：{missing_ov}')
    pages = {'index.html': index_page(models), 'conversions.html': conversions_page()}
    for m in models: pages[f'recipes/{m["slug"]}.html'] = recipe_page(m)
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT / 'recipes').mkdir(parents=True)
    vend = SITE / 'assets' / ASSET_VER
    if '--fonts' in sys.argv:
        (vend / 'fonts').mkdir(parents=True, exist_ok=True)
        allt = ''.join(html.unescape(re.sub(r'<[^>]+>', ' ', p)) for p in pages.values()) + (SITE / 'static/site.js').read_text(encoding='utf-8')
        build_fonts(allt, vend / 'fonts')
    shutil.copytree(vend, OUT / 'assets' / ASSET_VER)
    shutil.copy(SITE / 'static/site.css', OUT / 'assets/site.css')
    shutil.copy(SITE / 'static/site.js', OUT / 'assets/site.js')
    for name, page in pages.items(): (OUT / name).write_text(page, encoding='utf-8')
    (OUT / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
    (OUT / '.nojekyll').write_text('', encoding='utf-8')
    probs = lint(pages) + ['外文原句沒有中文說明：' + x for x in DROPPED]
    for m in models: probs += number_guard(m)
    # 字型涵蓋檢查
    fonts_dir = vend / 'fonts'
    print(f'產生 {len(pages)} 頁 → {OUT}')
    if probs:
        print('需要處理：'); [print('  ' + p) for p in probs]
        sys.exit(1)
    print('白話檢查、數字來源檢查：通過')

if __name__ == '__main__':
    main()
