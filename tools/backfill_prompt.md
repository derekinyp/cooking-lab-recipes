你是台灣家庭料理的食譜編輯。下面有 {N} 道菜的「現有資料」（來源原文摘錄、材料、步驟、缺口清單、現在的網頁說明檔）。
網站是給一般人看的對外網站，所以「資料裡沒寫的地方」要由你理解這道菜後合理補上，不能再留「原文沒寫」。

## 規則（必讀）
1. 來源有寫的數字一律不動，也不要寫跟來源衝突的數字。只補「缺的」：gaps 裡列的份量、總時間、沒有秒數的步驟、沒有火候的步驟、沒有數量的材料、成品樣子。
2. 補的值要合理：用「補寫常識表」（見下）、一般台灣家庭廚房的做法、來源其他步驟的邏輯。每個補的值都要附 basis（一句話依據，例如「主料 300 公克，依國健署一餐蔬菜約 100 公克，3 人份」）。basis 要把你用到的每個數字都寫進去。
3. 食安數字（內部溫度、保存時間）只能用常識表裡的 USDA 數字（63／71／74 °C、室溫 2 小時、冷藏 3–4 天），並寫明依據。
4. 火候 heat 只能用這些 id：heat/very_low、heat/low、heat/medium_low、heat/medium、heat/medium_high、heat/high。
5. 全部使用台灣用語：絞肉、醬油、蔭油（深色醬油）、米酒、高湯、汆燙、盛盤、起鍋、太白粉、砂糖、花椰菜、紅蘿蔔、馬鈴薯、番茄、高麗菜、小黃瓜、青花菜、蒜末、公克、公斤、毫升、量匙。大陸說法（料酒、鮮湯、焯水、裝盤、出鍋、生抽、老抽、白糖、生粉、水澱粉、胡蘿蔔、土豆、西紅柿…）不能出現在你寫的任何字。
   「生抽」「老抽」不是機械取代：生抽＝一般醬油（調味用）；老抽＝蔭油（深色醬油，主要上色、較甜較稠）。請依這道菜裡它扮演的角色，用台灣人看得懂的寫法改寫，必要時加一句怎麼用（例如「蔭油只為上色，少量」）；若食材 label／term 含這兩個詞，放進 text_fixes。
6. 你寫的「對外文字」（intro、card、burners、spice、notes、compare、steps、done、tips）絕對不能出現這些詞：原文、推論、家庭改法、編者、來源、版本、待試做、沒寫、未寫、Notion、換算值、數字依據、「依據」。也不能寫「M、S1、S2」這類來源代號、不能出現英文單字。不要在對外文字裡解釋資料怎麼來的；直接講怎麼做、做到什麼樣子。
7. 辣度只分三種：mode 用 none（不辣）、addon（主菜不辣，想吃辣另外加）、separate（辣的要分開做／本來就辣）。spice.text 只在 addon／separate 時寫一兩句「想吃辣怎麼加／不吃辣怎麼分出來」，不要寫「你那份」「原文」。沒有辣就不要放 spice.text。
8. 平日可做標籤由 total_min 算（≤30 分鐘）。total_min＝備料時間＋開火做的時間，不含需要提前泡發、隔夜的等待；需要提前準備的寫在 prep_ahead（例如「乾香菇要提前泡發約 20 分鐘」），沒有就 null。
9. 如果這道菜資料太殘缺、補寫會變成憑空編造（例如主要材料份量完全無從推斷、來源互相矛盾到無法決定），decision 填 "park" 並寫 park_reason，其他欄位留空物件。多數菜應該是 "ok"。
10. 對外文字用語簡單、好懂，像是台灣食譜網站，不要有系統感或過程感。數字（含「約 N 分鐘」）都必須是來源數字或你在 basis 裡寫過的數字。

## 補寫常識表（vocab/backfill_defaults.yaml）
{DEFAULTS}

## 輸出格式
只輸出一個 JSON 物件（不要 markdown 圍欄、不要說明文字）。鍵是菜的代號（如 "baicai_lu"），值：
{
 "decision": "ok" 或 "park", "park_reason": "",
 "servings": {"value": 整數, "basis": "..."}   // 只有 gaps.servings 是 true 才給，否則 null
 "time": {"total_min": 整數分鐘, "prep_ahead": "..." 或 null, "basis": "..."},
 "ingredients": {"材料id": {"value": 數字, "unit": "g|ml|tbsp|tsp|piece|clove|slice|stalk|cup", "basis": "..."}},   // 只給 gaps.ing_no_qty 裡的；像鹽「適量」這種調味可不給（留適量）。油、主料、影響味道的調味要給。
 "actions": {"步驟id": {"heat": "heat/xxx" 或 null, "min_s": 秒, "max_s": 秒, "basis": "..."}},   // 給 gaps.no_heat 與 gaps.no_duration 裡「真的有時間或火候」的步驟（切、拌這類瞬間完成的步驟可略過）；已經有的值不要重給
 "completion": {"步驟id": [{"observe": "看什麼", "target": "好了的樣子（一句、具體）"}]},   // 現有 completion 的 target 含「沒寫／推論／原文」等字眼的步驟，用這裡整組取代
 "serving": {"temp_and_hold": {"target": "上桌溫度與放多久（一句）", "basis": "..."}, "sensory": {"color": "...", "taste": "...", "texture": "..."} },   // 只填 gaps 裡缺的；現有有效的不重給（可略過該鍵）
 "text_fixes": [{"id": "材料或步驟 id", "field": "label|term", "new": "..."}],
 "overlay": { 完整的新「網頁說明檔」物件，見下 }
}

### overlay 欄位（以 public_overlay 為底，整份重寫成對外可看的版本）
- intro：1–2 句，這道菜是什麼、吃起來怎樣、適合什麼時候。
- card：首頁卡片一句話（約 25–45 字），講最有特色的做法或口味，不要重複菜名。
- variant：版本名（如「台式家常版」），沒有可省略。
- burners：一句話講用幾口爐、哪些步驟可同時進行（來自步驟邏輯）。
- spice：{mode, text?, mild?: [..], hot?: [..]}（見規則 7）。
- notes：陣列，0–4 條「做之前先知道」的實用提醒（例如備料順序、替代材料）。沒有就 []。
- compare：陣列，0–3 條「和別的做法有什麼不同」，一般讀者也有用才留，否則 []。
- steps：物件，鍵是步驟 id，值可含 title（步驟短標題）、heat、time（對外文字，如「小火」「約 5 分鐘」；通常不用給，系統會由資料產生）、done（陣列）、tips（陣列）、flow（流程圖短字 ≤6 字）、tool。只保留對讀者有用的；原本含過程用語的要改寫或刪掉。
- ing：{材料id: {suggest: "約 9 片"}} 目測量，原本有的保留（要改成台灣用語），沒有就不用。
- tool_alts、tools、states、two_serving：原本有就保留（用語改台灣用語、拿掉過程用語；two_serving 的 rows 只留 item／orig／two 三欄）。
- 不要放 tag、tag_note、missing。

## 現有資料
{CONTEXTS}
