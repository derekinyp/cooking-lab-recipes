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
    var text = new Fuse(recs, opts({ keys: [{ name: 'n', weight: 3 }, { name: 'a', weight: 2 }, { name: 'ax', weight: 2 }, { name: 'z', weight: 2 }, { name: 'i', weight: 1.5 }, { name: 'ia', weight: 1.2 }] }));
    var sound = new Fuse(recs, opts({ threshold: 0.2, keys: [{ name: 'p', weight: 2 }, { name: 'pi', weight: 1 }] }));
    var bySlug = {};
    recs.forEach(function (r) { bySlug[r.s] = r; });
    function has(list, q) { return (list || []).some(function (x) { return x.indexOf(q) >= 0; }); }
    // 排序分層：0 菜名含關鍵字；1 別名含關鍵字、或主要食材就是它；2 菜名模糊相近、讀音相近；3 只是其他食材沾到。同層再比相似度。
    function tierOf(r, q, hit) {
      if (CJK.test(q)) {
        if (r.n.indexOf(q) >= 0) return 0;
        for (var k = 0; k < (r.z || []).length; k++) if (r.z[k].indexOf(q) >= 0) return r.zt[k] === r.n || r.n.indexOf(r.zt[k]) === 0 ? 0 : 1;
        if (has(r.a, q) || has(r.ax, q)) return 1;
        if (has(r.mi, q)) return 1;
      }
      var key = hit.match && hit.match.key;
      if (hit.via === 'sound') return key === 'pi' ? 3 : 2;
      if (key === 'n' || key === 'a' || key === 'ax' || key === 'z') return 2;
      return 3;
    }
    function search(q) {
      q = String(q || '').replace(/\s+/g, ' ').trim();
      if (!q) return null;
      var res = {};
      function add(list, via, plus) {
        list.forEach(function (r) {
          var s = r.score + (plus || 0), cur = res[r.item.s];
          var m = (r.matches || [])[0] || null;
          if (m && m.key === 'z') { var zo = r.item.zt[m.refIndex]; m = { key: zo === r.item.n ? 'n' : (r.item.a.indexOf(zo) >= 0 ? 'a' : 'ax'), value: zo }; }  // 簡體字寫法 → 顯示原本的寫法；大陸說法不顯示
          if (m && m.key === 'ia') m = { key: 'ia', value: r.item.iz[m.refIndex] };  // 材料別名 → 顯示台灣說法
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
      var qq = CJK.test(q) ? q.replace(/\s/g, '') : q.toLowerCase();
      return Object.keys(res).map(function (k) { var h = res[k]; h.tier = tierOf(bySlug[h.slug], qq, h); return h; })
        .sort(function (a, b) { return a.tier - b.tier || a.score - b.score; });
    }
    function why(hit) {
      if (!hit) return '';
      var m = hit.match;
      if (hit.via === 'sound') return m && m.key === 'pi' ? '材料讀音相近：' + m.value : '讀音相近：' + hit.name;
      if (!m || m.key === 'n') return '';
      if (m.key === 'a' && (m.value === hit.name || hit.name.indexOf(m.value) === 0)) return '';
      if (m.key === 'a') return '也叫「' + m.value + '」';
      if (m.key === 'i') return '材料有「' + m.value + '」';
      if (m.key === 'ia') return '材料有「' + m.value + '」';
      return '';
    }
    return { search: search, why: why };
  }
  return { create: create, toPy: toPy };
});
