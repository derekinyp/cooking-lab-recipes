#!/usr/bin/env python3
"""把「會顯示給使用者的欄位」改成台灣用語（依 vocab/tw_terms.yaml）。

只改文字，不重排格式：逐行找 `欄位名: 值`（含花括號裡的寫法），只動值的部分。
不動：raw_text、evidence、title、url、note（內部筆記或來源原句）、id。
標了 rewrite: true 的詞（生抽、老抽）一詞多義，不在這裡機械取代，回報位置交給補寫批次。
用法：python3 tools/apply_tw_terms.py [--dry] 檔案或資料夾…
"""
import re, sys, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TW = yaml.safe_load((ROOT / 'vocab' / 'tw_terms.yaml').read_text(encoding='utf-8'))
RULES = [(re.compile(t.get('rx') or re.escape(t['cn'])), t['tw']) for t in TW['terms'] if not t.get('rewrite')]
REWRITE = [t['cn'] for t in TW['terms'] if t.get('rewrite')]
DISPLAY = ('label', 'term', 'summary', 'target', 'observe', 'raw', 'texture', 'color', 'taste', 'variant', 'zh_hant', 'qualitative',
           'risk', 'constraint', 'control', 'action', 'at', 'zh', 'alt', 'intro', 'card', 'burners', 'text', 'title', 'item', 'orig', 'two',
           'flow', 'tool', 'time', 'heat', 'temp', 'tag_note', 'tag')
KEY = re.compile(r'(?:^[ \t]*(?:-[ \t]+)?|(?<=[{,])[ \t]*)(?P<k>(?:' + '|'.join(DISPLAY) + r')):[ \t]*(?P<v>"(?:[^"\\]|\\.)*"|\'[^\']*\'|[^,}\n#]+)')

try:
    import opencc
    _cc = opencc.OpenCC('s2tw')
    # 和 site/build_site.py 的 s2t 同一套規則（繁簡同形的字不轉，免得「里脊」變「裡脊」）
    _AMBIG = set('干台只面后里才余云准几布松占当着征斗冲借制系历丑咸签卷向苏范钟致游注采术朴姜升合谷了志郁据弦恶')
    def s2t(s):
        s = str(s).replace('分钟', '分鐘').replace('小时', '小時')
        if any(c not in _AMBIG and _cc.convert(c) != c for c in s):
            s = _cc.convert(s)
        return s.replace('臺', '台')
except Exception:
    def s2t(s): return s

def tw(s):
    """先把簡體字轉繁體（站上本來就會轉），再換台灣用語。"""
    s = s2t(s)
    for rx, to in RULES: s = rx.sub(to, s)
    return s

def fix_text(text, content_mode=False):
    """content_mode：白話說明檔裡，所有值都是顯示文字，title 也要改。"""
    out = []
    for line in text.split('\n'):
        if content_mode:
            m = re.match(r'^(\s*(?:-\s+)?)([^\s:#][^:]*:\s+)(.*)$', line)
            if m and not m.group(2).strip().startswith(('slug', 'mode')):
                line = m.group(1) + m.group(2) + tw(m.group(3))
            elif re.match(r'^\s*-\s+', line) and ':' not in line.split('- ', 1)[-1][:20]:
                line = re.sub(r'^(\s*-\s+)(.*)$', lambda x: x.group(1) + tw(x.group(2)), line)
            else:
                line = line  # 其餘（續行）下面再處理
                if line.startswith(' ') and not re.match(r'^\s*[\w\u4e00-\u9fff./-]+:\s*', line): line = tw(line)
        else:
            def sub(m):
                if m.group('k') == 'title': return m.group(0)
                return m.group(0)[:m.start('k') - m.start()] + m.group('k') + ': ' + tw(m.group('v'))
            line = KEY.sub(sub, line)
        out.append(line)
    return '\n'.join(out)

def main():
    dry = '--dry' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    files = []
    for a in args:
        p = Path(a)
        files += sorted(p.glob('*.yaml')) if p.is_dir() else [p]
    changed = 0
    for f in files:
        t = f.read_text(encoding='utf-8')
        content_mode = 'site/content' in str(f.resolve())
        n = fix_text(t, content_mode)
        if n != t:
            changed += 1
            if not dry: f.write_text(n, encoding='utf-8')
        for w in REWRITE:
            c = sum(1 for l in n.split('\n') if w in l and not re.search(r'raw_text|evidence|note:', l))
            if c: print(f'  需理解後改寫：{f.name} 「{w}」 {c} 行')
    print(f'{"（試跑）" if dry else ""}改了 {changed} 個檔案')
if __name__ == '__main__': main()
