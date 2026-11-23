# 家常食譜網站（cooking-lab-recipes）

網址：https://derekinyp.github.io/cooking-lab-recipes/

這是一個自己在家做菜用的食譜網站，不給搜尋引擎收錄（每頁都有 noindex，`robots.txt` 全部禁止）。

## 裡面有什麼

- `recipes/`：17 道菜的食譜檔。每個數字都來自列出的原始食譜；原文沒寫的地方就標「原文沒寫」，不自己補。
- `vocab/`：做法、刀工、火候、材料等用詞表，產生網頁時用來把代碼換成中文。
- `site/`：產生網頁的程式（`build_site.py`）、每道菜的白話說明（`content/`）、每週新增清單（`weekly/`）與收錄規劃（`plan.yaml`，網站「收錄進度」頁）、湯匙換算表（`conversions.yaml`，出處是美國農業部食物資料庫 SR Legacy 與美國國家標準技術研究院的廚房量具換算）、樣式與字型。
- 首頁「找菜」：可以打菜名、別名、材料、同音字、簡體字或拼音找菜，也可以依中式家常／歐美經典、主要材料、菜系或地區、做法、要花多少時間分類篩選（可複選，顯示道數）。沒有開 JavaScript 時照樣列出全部菜色。
  - `site/facets.yaml`：分類規則（全部從食譜檔算出來，原文沒寫時間的歸「待試做計時」）。
  - `site/aliases.yaml`（由整理用的 120 道清單產生）與 `site/aliases_extra.yaml`（手動補充）：菜的別名。
  - `site/static/pinyin.json`：讀音表，由 `site/make_pinyin.py` 產生（需要 pypinyin，只有重做讀音表時才要）。
  - `site/static/find.js`：搜尋核心；`site/vendor/fuse.min.js`：模糊比對函式庫 Fuse.js 7.1.0（Apache 2.0，授權見 `site/vendor/fuse.LICENSE.txt`），放在本倉庫，不連外部網站。
  - `tests/test_search.js`：實際跑搜尋的測試（`node tests/test_search.js`，先產生網頁）。
- `docs/`：產生好的網頁，GitHub Pages 直接發布這個資料夾。

## 重新產生網頁

```
pip install pyyaml opencc fonttools brotli
python3 site/build_site.py          # 只產生網頁
python3 site/build_site.py --fonts  # 連字型子集一起重做（需要完整的思源黑體檔）
```

程式會檢查：頁面上沒有英文代碼或欄位名、白話說明裡的數字都能在食譜檔找到、每頁都有 noindex。檢查沒過就不輸出成功。

樣式依「振達設計規範 Workshop 1.2.1」。
