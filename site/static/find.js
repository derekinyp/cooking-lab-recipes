/* 首頁找菜的搜尋核心：菜名、別名、材料用模糊比對；同音字、簡體字、拼音用讀音比對。網頁和測試共用。 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else root.ZDFind = api;
})(this, function () {
  var CJK = /[\u3400-\u9fff]/;
  function pyMap(json) { var m = {}; for (var k in json) { var s = json[k]; for (var i = 0; i < s.length; i++) m[s[i]] = k; } return m; }
  function toPy(s, m) { var out = []; for (var i = 0; i < s.length; i++) { if (m[s[i]]) out.push(m[s[i]]); } return out.join(' '); }
  function create(Fuse, recs, pyJson) {
    var pm = pyJson ? pyMap(pyJson) : null;
    function opts(extra) {
      var o = { includeScore: true, includeMatches: true, ignoreLocation: true, threshold: 0.34, minMatchCharLength: 1 };
      for (var k in extra) o[k] = extra[k];
      return o;
    }
    var text = new Fuse(recs, opts({ keys: [{ name: 'n', weight: 3 }, { name: 'a', weight: 2 }, { name: 'z', weight: 2 }, { name: 'i', weight: 1.5 }] }));
    var sound = new Fuse(recs, opts({ threshold: 0.2, keys: [{ name: 'p', weight: 2 }, { name: 'pi', weight: 1 }] }));
    function search(q) {
      q = String(q || '').replace(/\s+/g, ' ').trim();
      if (!q) return null;
      var res = {};
      function add(list, via, plus) {
        list.forEach(function (r) {
          var s = r.score + (plus || 0), cur = res[r.item.s];
          var m = (r.matches || [])[0] || null;
          if (m && m.key === 'z') m = { key: m.value === r.item.n ? 'n' : 'a', value: r.item.zt[m.refIndex] };  // 簡體字寫法 → 顯示原本的寫法
          if (!cur || s < cur.score) res[r.item.s] = { slug: r.item.s, score: s, via: via, match: m, name: r.item.n };
        });
      }
      if (CJK.test(q)) {
        var qn = q.replace(/\s/g, '');
        add(text.search(qn), 'text', 0);
        if (pm) {
          // 同音字、簡體字：讀音要整段相同（不做模糊），免得「皮蛋」把每道有「蛋」的菜都找出來
          var qp = toPy(qn, pm);
          if (qp) recs.forEach(function (r) {
            var hit = null;
            r.p.forEach(function (x) { if (!hit && (' ' + x + ' ').indexOf(' ' + qp + ' ') >= 0) hit = { key: 'p', value: x }; });
            if (!hit) r.pi.forEach(function (x, k) { if (!hit && (' ' + x + ' ').indexOf(' ' + qp + ' ') >= 0) hit = { key: 'pi', value: r.i[k] }; });
            if (hit) add([{ item: r, score: hit.key === 'p' ? 0.05 : 0.15, matches: [hit] }], 'sound', 0);
          });
        }
      } else {
        var ql = q.toLowerCase();
        add(sound.search(ql).map(function (r) {
          var m = (r.matches || [])[0];
          if (m && m.key === 'pi') r.matches = [{ key: 'pi', value: r.item.i[m.refIndex] }];
          return r;
        }), 'sound', 0);
        add(text.search(ql), 'text', 0);
      }
      return Object.keys(res).map(function (k) { return res[k]; }).sort(function (a, b) { return a.score - b.score; });
    }
    function why(hit) {
      if (!hit) return '';
      var m = hit.match;
      if (hit.via === 'sound') return m && m.key === 'pi' ? '材料讀音相近：' + m.value : '讀音相近：' + hit.name;
      if (!m || m.key === 'n') return '';
      if (m.key === 'a' && (m.value === hit.name || hit.name.indexOf(m.value) === 0)) return '';
      if (m.key === 'a') return '也叫「' + m.value + '」';
      if (m.key === 'i') return '材料有「' + m.value + '」';
      return '';
    }
    return { search: search, why: why };
  }
  return { create: create, toPy: toPy };
});
