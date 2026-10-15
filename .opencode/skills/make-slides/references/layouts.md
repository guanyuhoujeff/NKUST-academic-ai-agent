# 六種版面與 deck.json 的寫法

一頁用哪種版面，看這頁要聽眾做什麼。

| layout | 什麼時候用 | 這頁要有的欄位 |
|---|---|---|
| `section` | 換段落，讓聽眾喘口氣 | `title`；可加 `kicker`、`subtitle` |
| `assertion` | 一句結論＋支持它的 3–5 個證據（最常用） | `title`、`bullets` |
| `bignumber` | 這頁的重點就是一個數字 | `title`、`number`、`caption`、`bullets`（3 條） |
| `table` | 要並排比較多筆資料（例如多篇文獻） | `title`、`table`（第一列是欄名，至少 4 列資料、3 欄，最多 12 列） |
| `compare` | 兩種情況、兩個時期、兩種做法的對照 | `title`、`left`、`right`（各有 `heading`、`bullets` 3 條） |
| `quote` | 原文說得比你好，直接引用 | `title`、`quote`；可加 `by` |

每一頁都可以加 `kicker`（標題上方的小字，例如「發現 1」）和 `note`（頁尾小字，適合放資料來源）。

## 圖示（icon）

每一頁都可以加 `"icon"`，畫在標題右上角（章節頁畫在右側），用的是 PowerPoint 原生圖形，可以直接點選修改顏色或大小：

| icon | 圖形 | 適合的頁 |
|---|---|---|
| `speed` | 閃電 | 加速、即時、毫秒 |
| `growth` / `decline` | 上／下箭頭 | 提升、成長／降低、下跌 |
| `compare` | 左右箭頭 | 兩者對照 |
| `data` | 資料庫 | 資料、樣本、筆數 |
| `method` | 齒輪 | 模型、方法、架構 |
| `paper` | 文件 | 文獻、引言 |
| `key` | 星星 | 重點、結論 |
| `target` | 靶心 | 目標、要解決的事 |
| `chart` | 長條圖 | 大數字、統計結果 |
| `warning` | 三角形「!」 | 風險、限制、誤差 |
| `question` | 圓形「?」 | 提問頁 |
| `money` / `percent` / `check` | 圓形「$」「%」「✓」 | 價格、比率、確認 |

不寫 `icon` 時，程式依標題裡的字自動挑一個（例如標題有「加速」就用 speed），都對不到就依版面挑；寫 `"icon": "none"` 就不放。

## 要點要有具體事實

每條要點盡量帶一個從來源原樣抄的具體事實：數字、年份、樣本數、倍數、方法或作者名稱。
assertion 和 compare 頁帶數字、英文名稱或「」引文的要點**不到 2 條**，build 的 `[份量]` 檢查會擋下來。

## 份量下限（build 的 `[份量]` 會檢查）

一頁只有一兩行，聽眾會覺得沒內容。寫每一頁前先回來源檔找材料：樣本、期間、方法、數字結果、作者的解釋、限制。

| layout | 要點數 |
|---|---|
| `assertion` | 3–4 條 |
| `bignumber` | 數字下面 3 條 |
| `compare` | 左右各 3 條 |
| `table` | 至少 4 列資料（不含欄名）、3 欄 |

每條是一句 15–70 字的完整事實（compare 45 字內、bignumber 55 字內），把數字和來源裡的條件、比較對象或作者的解釋一起寫，例如「先離線用 80,000 組蒙地卡羅模擬資料訓練網路，再線上用確定性優化器校準」，不是「離線學習」這種關鍵字或半句話。開頭可以加冒號小標（例如「訓練資料：…」），會自動加粗，不加也可以。

湊數不算，build 一樣會擋：只寫作者年份的要點（「Ruf & Wang (2020) 指出此策略」）、要點裡寫文獻卡的行號（「第 50 行」）、把一句拆成兩條、同一個數字出現在 3 頁以上。出處放 `note`。

`slides.py` 在叫你寫 deck.json 時會附上【材料包】：依大綱每頁的標題與引文，從來源檔挑出最相關的段落。要點優先從材料包挑。

| 不好（形容） | 好（事實） |
|---|---|
| 預測精度提升，擬合度高 | 相對誤差穩定低於 0.5% |
| 計算速度大幅加快 | 比 Monte Carlo 加速 9,000–16,000 倍 |

## deck.json 範例

```json
{
  "title": "選擇權定價文獻速覽",
  "subtitle": "從 The Journal of Finance 到台灣權證市場",
  "theme": "academic",
  "sources": ["literature.md", "notes/某篇文獻卡.md"],
  "slides": [
    {"layout": "section", "kicker": "第一部分", "title": "頂刊十年只有 11 篇直接談選擇權定價"},
    {"layout": "bignumber", "title": "The Journal of Finance 2015 年以後僅 11 篇",
     "number": "11", "caption": "篇論文的標題或摘要含 option pricing",
     "bullets": ["期刊以 ISSN 0022-1082 限定，不靠刊名", "（第二條：來源裡的另一個事實）"]},
    {"layout": "table", "title": "被引最高的三篇都在談報酬與波動，不是定價公式",
     "table": [["年份", "作者", "標題", "被引數"], ["2019", "IAN W. R. MARTIN, Christian Wagner", "What Is the Expected Return on a Stock?", "220"]],
     "note": "資料來源：OpenAlex"},
    {"layout": "assertion", "kicker": "第二部分", "title": "台灣權證市場提供了頂刊沒有的角度：個股新聞",
     "bullets": ["研究期間為 2014 年 1 月至 2020 年 12 月", "總觀察樣本數為 3,347,680 筆", "（第三條：來源裡的另一個事實）"]},
    {"layout": "compare", "title": "同一則新聞，上市初期擴大價差、到期前縮小價差",
     "left": {"heading": "上市後前 20 天", "bullets": ["媒體曝光度與價差顯著正相關", "（第二條：來源裡的另一個事實）"]},
     "right": {"heading": "到期前最後 20 天", "bullets": ["各項新聞變數與價差顯著負相關", "（第二條：來源裡的另一個事實）"]}},
    {"layout": "quote", "title": "作者把新聞稱為無內含價值權證的投機催化劑",
     "quote": "（從來源檔原樣抄一句）", "by": "作者，出處"}
  ]
}
```

- `sources` 一定要填：程式會拿這些檔案核對投影片裡的數字。
- 封面由 `title`、`subtitle` 自動產生，不用寫在 `slides` 裡。
- `slides` 每一頁的 `title` 要和 `outline.md` 裡確認過的標題一字不差。
