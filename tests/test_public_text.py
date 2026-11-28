#!/usr/bin/env python3
"""建置後掃描整個網站「使用者看得到的字」：過程用語、大陸用語、Notion 一律 0 筆；另外檢查卡片格式、時間標籤、辣度標籤、導覽列。
用法：先跑 python3 site/build_site.py（不可設 ZD_ALLOW_INCOMPLETE），再跑 python3 tests/test_public_text.py"""
import html, json, re, sys, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'
TW = yaml.safe_load((ROOT / 'vocab' / 'tw_terms.yaml').read_text(encoding='utf-8'))
SKIP = re.compile(r'<(script|style)[^>]*>.*?</\1>|<ol class="(?:card )?src-list">.*?</ol>', re.S)
ATTR = re.compile(r'(?:placeholder|aria-label|title|alt)="([^"]*)"')
fails = []

def visible(page):
    attrs = ' '.join(ATTR.findall(page))
    t = SKIP.sub(' ', page)
    t = re.sub(r'<[^>]+>', ' ', t)
    return html.unescape(t + ' ' + attrs)

pages = sorted(DOCS.rglob('*.html'))
if len(pages) < 50: fails.append(f'頁數太少：{len(pages)}')
hits = {'過程用語': 0, '大陸用語': 0, 'Notion': 0}
bad_re = [(ph, re.compile(re.escape(ph))) for ph in TW['forbidden_phrases']] + [('來源編號', re.compile('來源[①-⑳]')), ('沒寫', re.compile('沒寫|未寫'))]
cn_re = [(t['cn'], re.compile(t.get('rx') or re.escape(t['cn']))) for t in TW['terms']]
for p in pages:
    t = visible(p.read_text(encoding='utf-8'))
    rel = p.relative_to(DOCS)
    for ph, rx in bad_re:
        for m in rx.finditer(t):
            hits['Notion' if ph == 'Notion' else '過程用語'] += 1; fails.append(f'{rel}: 過程用語「{ph}」…{t[max(0, m.start()-12):m.end()+12].strip()}…')
    for cn, rx in cn_re:
        for m in rx.finditer(t):
            hits['大陸用語'] += 1; fails.append(f'{rel}: 大陸用語「{cn}」…{t[max(0, m.start()-12):m.end()+12].strip()}…')
    raw = p.read_text(encoding='utf-8')
    if re.search(r'notion\.(?:com|so)|app\.notion', raw, re.I): fails.append(f'{rel}: 還有 Notion 連結')
    if 'class="na"' in raw: fails.append(f'{rel}: 還有「沒資料」的占位字')
    if 'class="fb-' in raw or '我做了這道' in raw: fails.append(f'{rel}: 還有回饋按鈕')

# 網頁用的 JS 裡寫死的字串也不能有
for js in ('site.js', 'find.js'):
    t = (DOCS / 'assets' / js).read_text(encoding='utf-8')
    for ph, rx in bad_re + cn_re:
        if rx.search(t): fails.append(f'assets/{js}: 含「{ph}」')

# 導覽列
idx = (DOCS / 'index.html').read_text(encoding='utf-8')
for must_not in ('收錄進度', '每週新增', '換算表'):
    if must_not in visible(idx): fails.append(f'首頁還有「{must_not}」')
for must in ('最新食譜', '量匙換算'):
    if must not in visible(idx): fails.append(f'首頁缺少導覽「{must}」')

# 卡片：「約 N 分鐘・N 人份・辣度」；平日可做只給 30 分鐘內
cards = re.findall(r'<li class="dish-card card".*?</li>', idx, re.S)
if len(cards) < 50: fails.append(f'卡片只有 {len(cards)} 張')
for c in cards:
    slug = re.search(r'data-slug="([^"]+)"', c).group(1)
    meta = html.unescape(re.search(r'dc-meta">(.*?)</p>', c, re.S).group(1))
    m = re.fullmatch(r'約 (?:(\d+) 小時(?: (\d+) 分鐘)?|(\d+) 分鐘)・(\d+) 人份・(不辣|可另外加辣|辣)', meta)
    if not m: fails.append(f'{slug}: 卡片資訊格式不對：{meta}'); continue
    mins = int(m.group(3)) if m.group(3) else int(m.group(1)) * 60 + int(m.group(2) or 0)
    weekday = '平日可做' in c
    if weekday != (mins <= 30): fails.append(f'{slug}: 平日可做標籤與時間不符（{mins} 分鐘）')
    if not re.search(r'dc-intro">[^<]{10,}', c): fails.append(f'{slug}: 卡片沒有一句話介紹')
for slug in re.findall(r'data-slug="([^"]+)"', idx):
    pg = (DOCS / 'recipes' / f'{slug}.html').read_text(encoding='utf-8')
    if '約 ' not in pg or '人份' not in pg: fails.append(f'{slug}: 食譜頁缺時間或份量')
    if (ROOT / 'site' / 'content' / f'x').exists(): pass

print(f'掃描 {len(pages)} 頁：過程用語 {hits["過程用語"]} 筆、大陸用語 {hits["大陸用語"]} 筆、Notion {hits["Notion"]} 筆')
if fails:
    print(f'失敗 {len(fails)} 項：'); [print('  ' + x) for x in fails[:80]]
    sys.exit(1)
print('可見文字掃描、卡片格式、時間與辣度標籤：全部通過')
