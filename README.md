# 家常食譜網站（cooking-lab-recipes）

網址：https://derekinyp.github.io/cooking-lab-recipes/

這是一個自己在家做菜用的食譜網站，不給搜尋引擎收錄（每頁都有 noindex，`robots.txt` 全部禁止）。

## 裡面有什麼

- `recipes/`：15 道菜的食譜檔。每個數字都來自列出的原始食譜；原文沒寫的地方就標「原文沒寫」，不自己補。
- `vocab/`：做法、刀工、火候、材料等用詞表，產生網頁時用來把代碼換成中文。
- `site/`：產生網頁的程式（`build_site.py`）、每道菜的白話說明（`content/`）、湯匙換算表（`conversions.yaml`，出處是美國農業部食物資料庫 SR Legacy 與美國國家標準技術研究院的廚房量具換算）、樣式與字型。
- `docs/`：產生好的網頁，GitHub Pages 直接發布這個資料夾。

## 重新產生網頁

```
pip install pyyaml opencc fonttools brotli
python3 site/build_site.py          # 只產生網頁
python3 site/build_site.py --fonts  # 連字型子集一起重做（需要完整的思源黑體檔）
```

程式會檢查：頁面上沒有英文代碼或欄位名、白話說明裡的數字都能在食譜檔找到、每頁都有 noindex。檢查沒過就不輸出成功。

樣式依「振達設計規範 Workshop 1.2.1」。
