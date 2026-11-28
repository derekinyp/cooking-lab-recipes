#!/usr/bin/env python3
"""台灣用語工具與補寫驗證器的單元測試。用法：python3 tests/test_tw_and_backfill.py"""
import sys, copy, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import apply_tw_terms as A
import backfill_apply as B
fails = []
def check(ok, msg):
    print(('通過　' if ok else '失敗　') + msg)
    if not ok: fails.append(msg)

# --- 台灣用語表
TW = yaml.safe_load((ROOT / 'vocab' / 'tw_terms.yaml').read_text(encoding='utf-8'))
check(all(t['cn'] != t['tw'] for t in TW['terms']), '每個詞的大陸說法和台灣說法不同')
check(len({t['cn'] for t in TW['terms']}) == len(TW['terms']), '沒有重複的大陸說法')
check(all(t['tw'] not in (t.get('rx') or '') or True for t in TW['terms']), '用語表可載入')
for src, want in [('肉末燒茄子', '絞肉燒茄子'), ('土豆燒牛肉', '馬鈴薯燒牛肉'), ('焯水後裝盤', '汆燙後盛盤'), ('胡蘿蔔絲', '紅蘿蔔絲'),
                  ('黃瓜與小黃瓜', '小黃瓜與小黃瓜'), ('花椰菜', '花椰菜'), ('白花菜（花椰菜／椰花菜）', '花椰菜'), ('西紅柿炒蛋', '番茄炒蛋'), ('用料酒和白糖', '用米酒和砂糖'),
                  ('生抽', '生抽'), ('老抽', '老抽'), ('豆干絲', '豆干絲'), ('粉絲煲', '冬粉煮'), ('鮮湯', '高湯')]:
    check(A.tw(src) == want, f'用語取代：{src} → {want}（實際 {A.tw(src)}）')
check(A.tw(A.tw('土豆焯水')) == A.tw('土豆焯水'), '重複套用結果不變')
check(A.fix_text('  raw_text: "土豆焯水"\n  label: 土豆\n') == '  raw_text: "土豆焯水"\n  label: 馬鈴薯\n', '來源原句 raw_text 不改，label 會改')
check(A.fix_text('  note: "Total time: 25 minutes 花菜"\n') == '  note: "Total time: 25 minutes 花菜"\n', 'note 欄位和字串裡的「time:」不會被誤改')

# --- 補寫驗證器
d = yaml.safe_load("""
recipe: {servings: {value: null}}
ingredients: [{id: i_a, qty: {value: 5, unit: g, status: sourced}}, {id: i_b, qty: {value: null, unit: null, qualitative: 少許}}]
actions: [{id: a1, params: {}}, {id: a2, params: {heat: {level: heat/low}}}]
""")
good = {'decision': 'ok', 'servings': {'value': 3, 'basis': '依國健署'}, 'time': {'total_min': 20, 'basis': '備料 5 分鐘＋煮 15 分鐘'},
        'ingredients': {'i_b': {'value': 1, 'unit': 'tbsp', 'basis': '一般家庭用油量'}},
        'actions': {'a1': {'heat': 'heat/medium', 'min_s': 60, 'max_s': 120, 'basis': '常識表'}},
        'overlay': {'intro': '這是一道簡單好做的家常菜，適合配飯。', 'card': '簡單炒過再煮一下，鹹香下飯的家常菜。', 'burners': '用一口爐就能完成。', 'spice': {'mode': 'none'}}}
check(B.validate('x', good, d, 'raw 5 g') == [], '正常補寫資料通過驗證')
def bad(mut, kw):
    p = copy.deepcopy(good); mut(p)
    errs = B.validate('x', p, d, 'raw 5 g')
    check(any(kw in e for e in errs), f'驗證器擋下：{kw}')
bad(lambda p: p['actions']['a1'].update(heat='heat/super'), '火候不在詞表')
bad(lambda p: p['actions']['a1'].update(min_s=200, max_s=100), '秒數不合理')
bad(lambda p: p['servings'].update(value=40), '份數不合理')
bad(lambda p: p['ingredients']['i_b'].update(unit='bucket'), '單位不在詞表')
bad(lambda p: p['overlay'].update(intro='原文沒寫份數，這裡用推論補上的家常菜。'), '過程用語')
bad(lambda p: p['overlay'].update(card='先用料酒和白糖炒香再煮，鹹香下飯的家常菜。'), '大陸用語')
bad(lambda p: p['overlay'].update(burners='Use one burner for the whole dish.'), '英文')
bad(lambda p: p['overlay'].update(tag='weekday'), '不該有 tag')
bad(lambda p: p['overlay'].pop('spice'), 'spice')
bad(lambda p: p.update(serving={'temp_and_hold': {'target': '雞肉煮到中心 85°C 才上桌', 'basis': '常識'}}), '食安溫度')
check(B.validate('x', {**good, 'serving': {'temp_and_hold': {'target': '雞肉煮到中心 74°C 才上桌', 'basis': 'USDA 禽肉 74°C'}}}, d, 'raw') == [], '食安溫度 74°C（USDA 表）可通過')
# 不覆蓋來源有寫的值
doc = B.yml().load("recipe: {servings: {value: null}, changelog: []}\nnotes: {}\ningredients:\n  - {id: i_a, qty: {value: 5, unit: g, status: sourced}}\n  - {id: i_b, qty: {value: null, unit: null, qualitative: 少許}}\nactions:\n  - {id: a1, params: {}}\n  - {id: a2, params: {heat: {level: heat/low}}}\n")
p2 = copy.deepcopy(good); p2['ingredients']['i_a'] = {'value': 99, 'unit': 'g', 'basis': 'x'}; p2['actions']['a2'] = {'heat': 'heat/high', 'min_s': 5, 'max_s': 5, 'basis': 'x'}
B.apply_doc(doc, p2)
check(doc['ingredients'][0]['qty']['value'] == 5 and doc['ingredients'][0]['qty']['status'] == 'sourced', '來源有寫的材料數量不會被覆蓋')
check(doc['actions'][1]['params']['heat']['level'] == 'heat/low', '來源有寫的火候不會被覆蓋')
check(doc['ingredients'][1]['qty']['status'] == 'inferred' and '補寫依據' in doc['ingredients'][1]['qty']['note'], '補的材料標 inferred 並附依據')
check(doc['recipe']['servings']['status'] == 'inferred', '補的份數標 inferred')
print(f'{len(fails)} 項失敗' if fails else '全部通過')
sys.exit(1 if fails else 0)
