#!/usr/bin/env python3
"""驗證：和指定提交（預設 HEAD）相比，改動只有「台灣用語取代」，結構和數字都沒變，受保護欄位沒被動到。"""
import yaml, subprocess, glob, sys
sys.path.insert(0, 'tools')
import apply_tw_terms as A
base = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
PROT = ('raw_text', 'evidence', 'url', 'id')
bad = chg = 0
def cmp(a, b, path, f):
    global bad, chg
    if type(a) != type(b): print('型別不同', f, path); bad += 1; return
    if isinstance(a, dict):
        if list(a) != list(b): print('欄位不同', f, path); bad += 1; return
        for k in a: cmp(a[k], b[k], path + [k], f)
    elif isinstance(a, list):
        if len(a) != len(b): print('長度不同', f, path); bad += 1; return
        for i, (x, y) in enumerate(zip(a, b)): cmp(x, y, path + [i], f)
    elif isinstance(a, str):
        if a != b:
            chg += 1
            ks = [p for p in path if isinstance(p, str)]
            if A.tw(a) != b: print('不是用語取代', f, path, a[:40], '|', b[:40]); bad += 1
            if ks and ks[-1] in PROT: print('受保護欄位被改', f, path); bad += 1
            if 'site/content' not in f and ks and ks[-1] in ('note', 'title'): print('受保護欄位被改', f, path); bad += 1
    elif a != b: print('數值不同', f, path); bad += 1
for f in sorted(glob.glob('recipes/*.yaml') + glob.glob('site/content/*.yaml')):
    old = yaml.safe_load(subprocess.run(['git', 'show', f'{base}:{f}'], capture_output=True, text=True).stdout)
    cmp(old, yaml.safe_load(open(f, encoding='utf-8')), [], f)
print(f'不合格 {bad}，用語取代 {chg} 處')
sys.exit(1 if bad else 0)
