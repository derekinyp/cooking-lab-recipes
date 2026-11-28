#!/usr/bin/env python3
"""防呆測試：recipe.kind 不是 dish（基底）時，不計入菜數、不進搜尋資料。在暫存複本建置，不動工作目錄。
用法：python3 tests/test_kind_guard.py"""
import copy, json, re, shutil, subprocess, sys, tempfile, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
fails = []
def ok(c, msg):
    print(('通過　' if c else '失敗　') + msg)
    if not c: fails.append(msg)
def dump(d): return yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=4096)
def build(repo):
    p = subprocess.run([sys.executable, 'site/build_site.py'], cwd=repo, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr
def info(repo):
    idx = (repo / 'docs/index.html').read_text(encoding='utf-8')
    recs = json.loads(re.search(r'<script type="application/json" id="dish-index">([\s\S]*?)</script>', idx).group(1))
    return int(re.search(r'共 (\d+) 道', idx).group(1)), int(re.search(r'(\d+) 道家常菜', idx).group(1)), {r['s'] for r in recs}
tmp = Path(tempfile.mkdtemp()); repo = tmp / 'repo'
shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns('.git', 'docs', '__pycache__'))
try:
    rc, out = build(repo); ok(rc == 0, '基準建置成功')
    n0, k0, s0 = info(repo)
    src = yaml.safe_load((repo / 'recipes/lurou_fan.taiwan.home.yaml').read_text(encoding='utf-8'))
    comp = [c for c in src['components'] if c['call']['ref'].endswith('lurou_shouqie.ytower2020')][0]
    base = copy.deepcopy(comp['definition']); base['schema_version'] = src['schema_version']; base['serving'] = copy.deepcopy(src['serving'])
    base['notes'] = {'total_min': '90', 'time_basis': '測試'}; base['recipe']['servings'] = copy.deepcopy(src['recipe']['servings']); base['recipe']['status'] = 'machine_checked'
    ok(base['recipe']['kind'] == 'base', '測試用基底檔 kind: base')
    (repo / 'recipes/lurou_shouqie.ytower2020.yaml').write_text(dump(base), encoding='utf-8')
    op = repo / 'site/order.yaml'; op.write_text(op.read_text(encoding='utf-8').rstrip('\n') + '\n- lurou_shouqie\n', encoding='utf-8')
    rc, out = build(repo); ok(rc == 0, '加入基底檔後建置成功：' + out[-120:].replace('\n', ' '))
    n1, k1, s1 = info(repo)
    ok((n1, k1) == (n0, k0), f'基底不計入菜數（首頁「共 N 道」{n0}→{n1}、「N 道家常菜」{k0}→{k1}）')
    ok(s1 == s0 and 'lurou_shouqie' not in s1, '基底不在搜尋資料（dish-index）裡')
    ok((repo / 'docs/recipes/lurou_shouqie.html').exists() and 'lurou_shouqie' not in (repo / 'docs/index.html').read_text(encoding='utf-8'), '基底頁面仍會產生，但首頁沒有任何連結指向它')
    # 反向：同一份檔改成 kind: dish 就會計入（確認測試真的在量這個開關）
    base['recipe']['kind'] = 'dish'; (repo / 'recipes/lurou_shouqie.ytower2020.yaml').write_text(dump(base), encoding='utf-8')
    rc, out = build(repo); n2, k2, s2 = info(repo)
    ok(rc == 0 and n2 == n0 + 1 and 'lurou_shouqie' in s2, f'對照：同一份檔 kind 改成 dish 就會計入（{n0}→{n2}）')
    r = subprocess.run([sys.executable, 'tests/test_public_text.py'], cwd=repo, capture_output=True, text=True)
    ok(r.returncode == 0, '加入基底後，整站可見文字掃描仍是 0 筆')
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print('全部通過' if not fails else f'失敗 {len(fails)} 項'); sys.exit(1 if fails else 0)
