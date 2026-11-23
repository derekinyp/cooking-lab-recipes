#!/usr/bin/env python3
"""產生搜尋用的讀音表 site/static/pinyin.json（讀音 → 同音的字），讓打同音字、簡體字或拼音也找得到菜。
字的範圍：Big5 常用字（第一級）＋ GB2312 全部漢字；每個字只取一個讀音、不分聲調（做菜常見的多音字用菜名的讀法，見 FOOD）。
需要 pypinyin（只有重做讀音表時才要；平常產生網頁直接用做好的表）。
用法：python3 site/make_pinyin.py"""
import json
from pathlib import Path
from pypinyin import lazy_pinyin, Style
chars = set()
for hi in range(0xA4, 0xC7):
    for lo in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
        if (hi, lo) > (0xC6, 0x7E): continue
        try: c = bytes([hi, lo]).decode('big5')
        except UnicodeDecodeError: continue
        if '\u4e00' <= c <= '\u9fff': chars.add(c)
for hi in range(0xB0, 0xF8):
    for lo in range(0xA1, 0xFF):
        try: c = bytes([hi, lo]).decode('gb2312')
        except UnicodeDecodeError: continue
        if '\u4e00' <= c <= '\u9fff': chars.add(c)
# 做菜常見、但最常用讀音不是菜名讀法的字，改用菜名讀法；另補 Big5 常用字以外的菜名用字
FOOD = {'乾': 'gan', '茄': 'qie', '長': 'chang', '长': 'chang', '調': 'tiao', '调': 'tiao', '蛤': 'ge', '豉': 'chi', '焢': 'kong', '爌': 'kuang', '蚵': 'e', '粿': 'guo', '鯖': 'qing', '鯛': 'diao', '魠': 'tuo', '鮭': 'gui', '鱸': 'lu', '蘆': 'lu', '筍': 'sun', '笋': 'sun'}
chars |= set(FOOD)
by = {}
for c in sorted(chars):
    p = [FOOD[c]] if c in FOOD else lazy_pinyin(c, style=Style.NORMAL, errors='ignore')
    if p and p[0].isascii() and p[0].isalpha(): by.setdefault(p[0].replace('ü', 'v'), []).append(c)
out = Path(__file__).resolve().parent / 'static' / 'pinyin.json'
out.write_text(json.dumps({k: ''.join(v) for k, v in sorted(by.items())}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'{out}：{len(chars)} 字、{len(by)} 個讀音，{out.stat().st_size // 1024} KB')
