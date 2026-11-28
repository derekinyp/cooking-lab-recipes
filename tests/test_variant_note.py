#!/usr/bin/env python3
"""「也可以這樣做」：有 also 的代表菜頁面最下方出現；沒有的頁面沒有；過程用語整句不顯示。在暫存複本建置，不動 docs。"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; fails = []
def ok(c, m):
    print(('通過　' if c else '失敗　') + m)
    if not c: fails.append(m)
d = Path(tempfile.mkdtemp()) / 'r'; shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns('.git', 'docs'))
cp = d / 'site/content/sanbei_ji.taiwan.home.yaml'
cp.write_text(cp.read_text(encoding='utf-8').rstrip('\n') + '\nalso:\n- name: 可樂雞翅\n  text: 換成雞翅，來源①寫的醬油量照原來。\n- name: 黃燜雞\n  text: 換成雞腿肉，醬汁收乾一點。\n', encoding='utf-8')
r = subprocess.run([sys.executable, 'site/build_site.py'], cwd=d, capture_output=True, text=True)
h = lambda s: (d / 'docs/recipes' / f'{s}.html').read_text(encoding='utf-8')
ok(r.returncode == 0, '有 also 的說明檔可以建置')
ok('也可以這樣做' in h('kejia_xiaochao') and '豆干肉絲' in h('kejia_xiaochao') and h('kejia_xiaochao').rfind('also-h') > h('kejia_xiaochao').rfind('src-h'), '客家小炒：註記出現在參考食譜之後（最下方）')
ok('也可以這樣做' not in h('mapo_doufu'), '沒有 also 的頁面不出現這一節')
ok('黃燜雞' in h('sanbei_ji') and '可樂雞翅' not in h('sanbei_ji') and '來源①' not in h('sanbei_ji'), '含過程用語的那一句整句不顯示，其他句照常')
ok(not re.search(r'也可以這樣做', (d / 'docs/index.html').read_text(encoding='utf-8')), '首頁、搜尋不受影響（變體不獨立成頁、不進搜尋資料）')
print('全部通過' if not fails else f'失敗 {len(fails)} 項'); sys.exit(1 if fails else 0)
