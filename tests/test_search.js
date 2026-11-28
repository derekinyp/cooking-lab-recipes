// 實際跑首頁的搜尋：用產生好的 docs/ 裡的搜尋資料、讀音表與 Fuse.js，確認常見打法都找得到對的菜。
// 用法：node tests/test_search.js   （先跑 python3 site/build_site.py）
const fs = require('fs'), path = require('path');
const D = path.join(__dirname, '..', 'docs');
const Fuse = require(path.join(D, 'assets', 'fuse.min.js'));
const ZDFind = require(path.join(D, 'assets', 'find.js'));
const html = fs.readFileSync(path.join(D, 'index.html'), 'utf8');
const recs = JSON.parse(html.match(/<script type="application\/json" id="dish-index">([\s\S]*?)<\/script>/)[1]);
const py = JSON.parse(fs.readFileSync(path.join(D, 'assets', 'pinyin.json'), 'utf8'));
const f = ZDFind.create(Fuse, recs, py);
const name = s => (recs.find(r => r.s === s) || {}).n;
const cases = [
  ['菜脯', 'caipu_dan', 1, '菜名一部分'],
  ['蘿蔔乾', 'caipu_dan', 1, '別名、材料'],
  ['萝卜干', 'caipu_dan', 1, '簡體字'],
  ['西紅柿', 'fanqie_chaodan', 1, '別名（大陸說法）'],
  ['西红柿', 'fanqie_chaodan', 1, '簡體字'],
  ['蕃茄炒蛋', 'fanqie_chaodan', 1, '異體字別名'],
  ['三背雞', 'sanbei_ji', 1, '同音字'],
  ['麻婆逗腐', 'mapo_doufu', 1, '同音字'],
  ['宮爆雞丁', 'gongbao_jiding', 1, '別名'],
  ['魯肉飯', 'lurou_fan', 1, '別名'],
  ['干煸四季豆', 'ganbian_sijidou', 1, '別名（簡體寫法）'],
  ['sanbeiji', 'sanbei_ji', 1, '拼音'],
  ['mapo', 'mapo_doufu', 1, '拼音一部分'],
  ['五花肉', 'gaolicai_fan', 5, '主食材'],
  ['五花肉', 'lurou_fan', 5, '主食材'],
  ['豆腐', 'mapo_doufu', 2, '主食材'],  // 家常豆腐（W49）菜名也有豆腐，兩道真正以豆腐為主的菜排前 2 即可
  ['豆腐', 'jiachang_doufu', 2, '主食材'],
  ['高麗菜', 'gaolicai_fan', 1, '主食材'],
  ['捲心菜', 'gaolicai_fan', 1, '材料別名'],
  ['皮蛋', 'xia_pidan_shourou_zhou', 1, '主食材'],
  ['義大利麵', 'pasta_bianca', 3, '歐美經典'],
];
let fail = 0;
for (const [q, want, topN, kind] of cases) {
  const hits = f.search(q) || [];
  const rank = hits.findIndex(h => h.slug === want) + 1;
  const ok = rank >= 1 && rank <= topN;
  if (!ok) fail++;
  console.log(`${ok ? '通過' : '失敗'}　${kind}：「${q}」→ ${name(want)} 排第 ${rank || '—'}（要前 ${topN}）　結果：${hits.slice(0, 5).map(h => name(h.slug) + (f.why(h) ? '〔' + f.why(h) + '〕' : '')).join('、') || '無'}`);
}
// 排序規則：菜名含關鍵字 → 別名或主要食材 → 菜名模糊／讀音相近 → 其他食材沾到
const rankCases = [
  // [搜尋字, 必須排在前面的菜, 必須排在後面的菜, 說明]
  ['蘿蔔乾', 'caipu_dan', 'baicai_lu', '蘿蔔乾是菜脯蛋的主要食材，白菜滷只有紅蘿蔔絲，要排在後面'],
  ['蘿蔔乾', 'caipu_dan', 'luobo_paigu_tang', '菜脯蛋（別名、主食材）要在蘿蔔排骨湯（菜名只有蘿蔔）前面'],
  ['蘿蔔', 'luobo_paigu_tang', 'baicai_lu', '菜名含蘿蔔的排前面，只用到紅蘿蔔絲的白菜滷排後面'],
  ['豆腐', 'mapo_doufu', 'baicai_lu', '菜名含豆腐的排前面'],
  ['豆腐', 'jiachang_doufu', 'baicai_lu', '菜名含豆腐的排前面'],
];
for (const [q, first, later, why] of rankCases) {
  const hits = f.search(q) || [];
  const a = hits.findIndex(h => h.slug === first), b = hits.findIndex(h => h.slug === later);
  const ok = a >= 0 && (b < 0 || a < b);
  if (!ok) fail++;
  console.log(`${ok ? '通過' : '失敗'}　排序：「${q}」${name(first)} 排第 ${a + 1 || '—'}、${name(later)} 排第 ${b + 1 || '（沒出現）'}　${why}`);
}
{ // 分層必須從小到大，不能後面的層冒到前面
  const hits = f.search('蘿蔔乾') || [];
  const ok = hits.every((h, i) => i === 0 || hits[i - 1].tier <= h.tier);
  if (!ok) fail++;
  console.log(`${ok ? '通過' : '失敗'}　排序：「蘿蔔乾」結果依層級由前到後`);
  const top = hits[0];
  if (!top || top.slug !== 'caipu_dan' || top.tier > 1) { fail++; console.log('失敗：「蘿蔔乾」第一個必須是菜脯蛋（別名或主食材層）'); }
}
{ // 菜名完全對上的排最前面
  const hits = f.search('三杯雞') || [];
  const ok = hits[0] && hits[0].slug === 'sanbei_ji' && hits[0].tier === 0;
  if (!ok) fail++;
  console.log(`${ok ? '通過' : '失敗'}　排序：菜名完全相同的「三杯雞」排第 1 且在菜名層`);
}
{ // 找不到就是找不到
  const hits = f.search('火星人') || [];
  const ok = hits.length === 0;
  if (!ok) fail++;
  console.log(`${ok ? '通過' : '失敗'}　沒有相關的字不會亂找（「火星人」找到 ${hits.length} 道）`);
}
{ // 打大陸說法要找得到，但畫面上顯示的說明不能出現大陸說法
  const CN = ['西紅柿', '胡蘿蔔', '土豆', '西蘭花', '包菜', '卷心菜', '里脊', '肉末', '料酒', '白糖', '生抽', '老抽', '鮮湯', '花菜', '黃瓜'];
  const shown = new Set();
  for (const q of ['西紅柿', '胡蘿蔔', '土豆', '包菜', '卷心菜', '花菜', '料酒', '肉末', '里脊', '粉絲', '黃油', '乾鍋花菜', '西红柿', '胡萝卜']) {
    for (const h of (f.search(q) || [])) shown.add(f.why(h));
  }
  const leaked = [...shown].filter(t => CN.some(w => t.includes(w)));
  if (leaked.length) { fail++; console.log('失敗：搜尋結果的說明出現大陸用語：' + leaked.join('、')); } else console.log('通過　搜尋結果的說明沒有大陸用語');
  for (const [q, want] of [['西紅柿', 'fanqie_chaodan'], ['胡蘿蔔', 'luobo_paigu_tang'], ['乾鍋花菜', 'ganguo_huacai']]) {
    const rank = (f.search(q) || []).findIndex(h => h.slug === want) + 1;
    if (!rank || rank > 6) { fail++; console.log(`失敗：打大陸說法「${q}」要找得到 ${name(want)}`); } else console.log(`通過　大陸說法「${q}」仍找得到 ${name(want)}（第 ${rank}）`);
  }
}
if (fail) { console.log(`${fail} 項沒過`); process.exit(1); }
console.log(`搜尋測試全部通過（${cases.length} 項）`);
