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
// 不相干的字不該把整個菜單都找出來
const noise = (f.search('蘿蔔乾') || []).length;
console.log(`「蘿蔔乾」共找到 ${noise} 道`);
if (noise > 3) { fail++; console.log('失敗：「蘿蔔乾」找到太多不相干的菜'); }
if (fail) { console.log(`${fail} 項沒過`); process.exit(1); }
console.log(`搜尋測試全部通過（${cases.length} 項）`);
