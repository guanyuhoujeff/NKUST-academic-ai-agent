---
name: analyze-literature
description: 分析文獻、整理論文重點、做文獻卡時使用。把 papers/ 裡的每一篇 PDF 交給 NotebookLM 分析，每篇產出一張文獻卡 notes/<檔名>.md。
---

# 分析文獻

讀論文的是 NotebookLM（Google 的文獻工具，回答會附原文出處），你負責指揮它、檢查產出物。工具是 `nlm` 指令。

## 步驟

### 0. 確認 nlm 裝好、登入了
1. 執行 `nlm --version`。
   - 有版本號 → 到第 2 點。
   - 找不到指令 → 先執行 `python --version`（Windows 的 `python` 無效時改用 `py`），**必須是 3.11 以上**；版本太舊或沒有 Python，停下來請使用者到 https://www.python.org/downloads/ 安裝最新版（安裝時勾選 Add python.exe to PATH），裝完重開 OpenCode 再繼續。
   - Python 版本夠 → 執行 `python -m pip install --user notebooklm-mcp-cli`。約 150 MB，正常網路 1–2 分鐘；若超過 5 分鐘還沒好，告訴使用者可能是網路問題。裝完執行 `python -m notebooklm_tools.cli.main --version` 確認有版本號。
2. 執行 `nlm login --check`（或 `python -m notebooklm_tools.cli.main login --check`）。
   - 看到 `Authenticated` → 繼續。
   - 失敗或顯示過期 → 停下來請使用者**自己在終端機執行 `nlm login`**（會開瀏覽器登入 Google），完成後再叫你繼續。你不能代替使用者登入。提醒使用者：**建議用一個專門給 AI agent 的 Google 帳號登入，不要用平常收信的那個**——這個 skill 會在該帳號裡建立 notebook。

### 1. 列出要分析的論文
列出 `papers/` 資料夾裡所有 `.pdf`。一篇都沒有就停下來告訴使用者。
已經有對應 `notes/<檔名>.md` 的論文跳過，不重做。

### 2. 逐篇分析
對每一篇 PDF 執行：

```
python .opencode/skills/analyze-literature/scripts/analyze.py papers/<檔名>.pdf
```

（Windows 若 `python` 無效，改用 `py`。）

這支程式會：建一個 NotebookLM notebook → 上傳 PDF → 用 `references/main_prompt.md` 的提示詞提問 → 把回答寫成 `notes/<檔名>.md`，並把完整回傳存成 `notes/<檔名>.json`。
一篇約 2–4 分鐘，**一篇做完再做下一篇**，不要同時跑多篇。

篇數超過 20 篇時，每一行都加上 `--cleanup`：分析完就刪掉該篇的 notebook。免費帳號的 notebook 有數量上限（約 100 本），不刪會滿。代價是文獻卡上的 NotebookLM 連結會寫「分析後已刪除」，之後要換角度再問就得重新上傳。

### 3. 需要其他角度時：換 prompt 再問
`references/` 裡每一份 `<名稱>_prompt.md` 都是一種分析角度，`main_prompt.md` 是預設的五步分析。要用別的角度（例如只拆解計量方法）就指定它：

```
python .opencode/skills/analyze-literature/scripts/analyze.py papers/<檔名>.pdf --prompt references/<名稱>_prompt.md
```

產出為 `notes/<檔名>.<名稱>.md`。同一篇 PDF 不會重新上傳，程式會沿用第一次建立的 notebook。

### 4. 做總表
全部做完後寫 `notes/README.md`：一張表格，每篇一列，欄位為：檔名｜文獻卡連結｜NotebookLM 連結（取自文獻卡開頭的 `notebook:`）。

## 產出物格式
每篇 PDF 在 `notes/` 留下：
- `<檔名>.md`：文獻卡。開頭是五行資訊（來源 PDF、用的 prompt、NotebookLM 連結、日期、產生者），接著是 NotebookLM 的回答原文，最後是「附錄：引用的原文片段」，列出回答裡每個 `[n]` 對應的原文。
- `<檔名>.<名稱>.md`：用其他 prompt 分析的結果，格式同上。
- `<檔名>.json`：notebook 資訊與每次提問的完整回傳，供日後核對。

## 檢查（交出去之前一定要做）

1. `papers/` 有幾個 PDF，`notes/` 就要有幾個 `<檔名>.md`（不算 README.md，也不算 `<檔名>.<名稱>.md`）。
2. 每張文獻卡都含有五個段落標題：文獻引用資訊、研究核心目的、研究方法與設計、實證結果摘要、結論建議與限制。
3. **文獻卡內容是 NotebookLM 的回答原文，你不可以改寫、刪減或補充。** 你覺得哪裡不對，寫在回報裡，不要動檔案。
4. `notes/README.md` 存在，而且每篇 PDF 都在表格裡有一列。
5. 回報時列出每篇的字數與引用筆數（程式最後一行會印）。

## 失敗怎麼辦

- 程式印出 `nlm ... 失敗`：看訊息。提到 expired／authentication → 回到步驟 0。其他錯誤重跑同一篇一次，再失敗就**跳過這篇、繼續做下一篇**，最後回報哪一篇沒做成與錯誤訊息。不要把 PDF 複製到別的位置再試——NotebookLM 拒收某個檔案時，換位置不會成功。
- 單篇超過 15 分鐘沒結束：中止，重跑一次。
- 任何一項檢查沒過：先修再回報。
