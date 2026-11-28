# 家常食譜網站（cooking-lab-recipes）

網址：https://derekinyp.github.io/cooking-lab-recipes/

這是一個自己在家做菜用的食譜網站，不給搜尋引擎收錄（每頁都有 noindex，`robots.txt` 全部禁止）。

## 裡面有什麼

- `recipes/`：50 道菜的食譜檔。來源有寫的數字一律照來源；來源沒寫的份量、時間、火候、用量，由編輯依常識表（`vocab/backfill_defaults.yaml`）合理補上，資料裡標 `status: inferred` 並在 `note` 寫「補寫依據」。網站上不會出現「原文沒寫」「推論」這類過程用語。
- `vocab/`：做法、刀工、火候、材料等用詞表，產生網頁時用來把代碼換成中文。
- `site/`：產生網頁的程式（`build_site.py`）、每道菜的白話說明（`content/`）、最新食譜清單（`weekly/`）與收錄規劃（`plan.yaml`，內部規劃用，網站不連結）、湯匙換算表（`conversions.yaml`，出處是美國農業部食物資料庫 SR Legacy 與美國國家標準技術研究院的廚房量具換算）、樣式與字型。
- 首頁「找菜」：可以打菜名、別名、材料、同音字、簡體字或拼音找菜，也可以依中式家常／歐美經典、主要材料、菜系或地區、做法、要花多少時間分類篩選（可複選，顯示道數）。沒有開 JavaScript 時照樣列出全部菜色。
  - `site/facets.yaml`：分類規則（全部從食譜檔算出來；時間分「平日可做（30 分鐘內）」「30–60 分鐘」「1 小時以上」，依 `notes.total_min`）。
  - `site/aliases.yaml`（由整理用的 120 道清單產生）與 `site/aliases_extra.yaml`（手動補充）：菜的別名。
  - `site/static/pinyin.json`：讀音表，由 `site/make_pinyin.py` 產生（需要 pypinyin，只有重做讀音表時才要）。
  - `site/static/find.js`：搜尋核心；`site/vendor/fuse.min.js`：模糊比對函式庫 Fuse.js 7.1.0（Apache 2.0，授權見 `site/vendor/fuse.LICENSE.txt`），放在本倉庫，不連外部網站。
  - `tests/test_search.js`：實際跑搜尋的測試，含排序（菜名 → 別名或主要食材 → 其他食材）與「大陸說法能搜到但不顯示」（`node tests/test_search.js`，先產生網頁）。
- `vocab/tw_terms.yaml`：台灣用語表。全站只用台灣用語；大陸說法（如土豆、料酒、焯水）只留成搜尋別名。`tools/apply_tw_terms.py` 套用到食譜檔與說明檔；`tools/verify_tw_only.py` 驗證改動只有用語取代。
- `tools/backfill_*.py`、`vocab/backfill_defaults.yaml`：補寫缺漏資料的工具與常識表（外部模型出草稿，程式驗證才寫入：不覆蓋來源數字、火候必須在詞表、食安數字只能用 USDA 表）。
- `tests/test_public_text.py`：建置後掃描所有頁面使用者看得到的字，過程用語、大陸用語、Notion 一律必須是 0 筆；也檢查卡片格式與時間、辣度標籤。
- `tests/test_tw_and_backfill.py`：用語表與補寫驗證器的單元測試。
- `docs/`：產生好的網頁，GitHub Pages 直接發布這個資料夾。

## 重新產生網頁

```
pip install pyyaml opencc fonttools brotli
python3 site/build_site.py          # 只產生網頁
python3 site/build_site.py --fonts  # 連字型子集一起重做（需要完整的思源黑體檔）
```

程式會檢查：頁面上沒有英文代碼或欄位名、沒有過程用語與大陸用語、白話說明裡的數字都能在食譜檔找到、每頁都有 noindex，另外每道菜都要有份量與總時間（`notes.total_min`）。檢查沒過就不輸出成功。

測試：

```
python3 site/build_site.py && node tests/test_search.js && python3 tests/test_public_text.py && python3 tests/test_tw_and_backfill.py
```

樣式依「振達設計規範 Workshop 1.2.1」。
