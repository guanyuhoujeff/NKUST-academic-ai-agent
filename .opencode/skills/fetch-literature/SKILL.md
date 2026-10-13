---
name: fetch-literature
description: 找學術文獻時使用。向 OpenAlex 查詢對照表裡的頂刊（或指定期刊）、指定主題的論文，產出附 DOI 的文獻清單 literature.md。
---

# 抓文獻

向 OpenAlex（免費公開的學術資料庫）查論文，交出一份每一筆都查得到的文獻清單。查詢由 `scripts/search.py` 執行：它讀期刊對照表、組網址、寫檔；你負責確認條件、跑程式、照實回報。

## 步驟

### 0. 確認 OpenAlex 金鑰
查詢要帶金鑰，否則會和同一個網路上的所有人共用一個很小的額度。金鑰放在環境變數 `OPENALEX_API_KEY`。

1. 用 Shell 工具查環境變數有沒有值。**只看有沒有值，不要把金鑰印出來**（畫面可能正在投影，印出來也會留在對話紀錄裡）：
   - Windows PowerShell：`if ($env:OPENALEX_API_KEY) { "有值" } else { "沒有值" }`
   - macOS／Linux：`[ -n "$OPENALEX_API_KEY" ] && echo 有值 || echo 沒有值`
2. **有值**：直接往下做。
3. **沒有值**：停下來請使用者提供金鑰，並附上申請網址 https://openalex.org/settings/api （免費，不用信用卡）。在使用者給金鑰之前不要往下做。
4. 使用者在對話中給了金鑰之後，**收到金鑰的第一個動作**是用 Shell 工具把它存進環境變數，**做完才可以開始查詢**：
   - macOS／Linux：`echo 'export OPENALEX_API_KEY="金鑰"' >> ~/.bashrc`，本次先 `export OPENALEX_API_KEY="金鑰"`
   - Windows：`setx OPENALEX_API_KEY "金鑰"`，本次先 `$env:OPENALEX_API_KEY="金鑰"`
   然後告訴使用者「金鑰已存入環境變數，重開 OpenCode 後生效；本次先直接用這把金鑰繼續」。

### 1. 確認三件事
- **主題關鍵字**：用英文，例如 `option pricing`。OpenAlex 收錄的論文幾乎都是英文，用中文查一定是 0 筆。
  - 使用者給的是英文 → 直接用。
  - 使用者給的是中文（例如「數位轉型」）→ **這一輪只做翻譯，不查詢**：列出 1–3 個你認為對應的英文學術用語（例如 `digital transformation`），請使用者選一個或自己改，然後結束。中文詞和英文術語常常對不上（例如「漂綠」是 `greenwashing`，不是 `green`），由使用者確認才不會查錯方向。使用者下一個指令給了英文詞，再往下做。
- **期刊**：使用者指定哪一本就查那一本（用 `--journal`）。使用者說「頂刊」、「頂尖期刊」或沒指定，就查對照表 `references/journals.md` 裡的全部期刊（程式預設）。「頂刊」指的就是這張表，不是要你自己想哪些期刊算頂刊。
- **起始年**：使用者有說才加 `--from`；沒說就不限。

### 2. 執行查詢
用 Shell 工具執行（關鍵字放在引號裡）：

```
python .opencode/skills/fetch-literature/scripts/search.py "option pricing"
python .opencode/skills/fetch-literature/scripts/search.py "greenwashing" --journal "The Journal of Finance" --from 2015
python .opencode/skills/fetch-literature/scripts/search.py "ESG" --n 30
```

- 程式會寫出工作資料夾的 `literature.md`，並印出：期刊範圍、查到幾筆、列了幾篇。
- 換了關鍵字再查，程式會先把原本的 `literature.md` 改名成 `literature-<舊關鍵字>.md` 保存，再寫新的；同一個關鍵字再查（例如加 `--n`）就直接覆蓋。程式印了「已改名保存為…」就一併告訴使用者。
- 使用者要更多篇 → 同樣的指令加 `--n 數字`（最多 200），其他條件不要動。
- **不要自己組 OpenAlex 網址去查**，也不要用 webfetch；期刊範圍、金鑰、網址都由程式處理。

### 3. 看程式印出來的結果
- **查到 N 筆（N > 0）** → 做步驟 4a。
- **查到 0 筆** → 做步驟 4b。
- 程式印出錯誤訊息（例如「對照表裡沒有這本」「關鍵字要用英文」「沒有金鑰」）→ 照訊息處理：缺期刊就走「新增期刊」，缺英文詞或金鑰就回到步驟 0 或 1 問使用者。

### 4a. 有結果：檢查後交出
1. 列出工作資料夾的檔案，確認 `literature.md` 在裡面；讀回來，確認表格列數等於程式說「列了幾篇」。
2. 確認每一列的 DOI 都以 `https://doi.org/` 開頭、期刊都在對照表裡。
3. 回覆使用者：查了什麼（關鍵字、期刊範圍、年份）、總共幾筆、列出前幾篇、檔案路徑。程式說「還有 X 篇沒列出」就一併說，使用者要更多就加 `--n`。
4. 標題、作者、DOI **照檔案原樣**，不可改寫、不可翻譯、不可補上檔案裡沒有的論文。

### 4b. 0 筆：回報並結束
0 筆通常不是程式錯，是「這些期刊不做這個主題」或「論文用的是別的說法」。這一輪到此結束，回覆使用者三件事：

1. 查了什麼：期刊範圍、英文關鍵字、起始年（沒限就寫不限），結果 0 筆。
2. 建議一，**換期刊**：對照表裡的期刊是為某個主題挑的，換主題就要換期刊。請使用者提供他領域的期刊（例如國科會學門期刊分級），照「新增期刊」加進來再查。
3. 建議二，**換說法**：提出 2–3 個英文同義詞（例如 digital transformation → digitalization、fintech）。

要不要換、換哪個，由使用者的下一個指令決定；這一輪不要自己換了再查，也不要自己加期刊。

### 新增期刊（對照表裡沒有，或使用者要整理一份期刊清單進來）
1. 對每一本期刊執行：
   ```
   python .opencode/skills/fetch-literature/scripts/journal.py lookup "刊名"
   ```
2. 看程式最後一行：
   - 「只有一本刊名完全相符，且是核心期刊」→ 可以直接執行它給的 `add` 指令。
   - 「沒有唯一完全相符的那一本」→ **停下來**，把候選清單貼給使用者，請他選是哪一本。同名期刊很常見（例如伊朗也有一本同名的 Journal of Finance），不可以自己猜。
3. `add` 的第二個參數是**等級，要寫出處**：
   - 使用者給了期刊分級清單（例如國科會「財金及會計學門」期刊分級報告），就照清單寫，例如 `"國科會 A+"`、`"國科會 A Tier-1"`。
   - 沒有可靠出處就寫 `"未查"`。**不可以自己判斷期刊好不好。**
4. 一次整理很多本時，做完列一張表回報：哪幾本加進去了、哪幾本等使用者選、哪幾本查不到。
5. 想看對照表現在有哪些期刊：`python .opencode/skills/fetch-literature/scripts/journal.py issns`。

## 程式在做什麼（給想看懂的人）
`search.py` 送出的網址長這樣（金鑰由程式從環境變數帶入）：

```
https://api.openalex.org/works?filter=primary_location.source.issn:【對照表的 ISSN，多本用|接】,primary_location.source.is_core:true,title_and_abstract.search:%22【關鍵字】%22[,from_publication_date:【起始年】-01-01]&sort=cited_by_count:desc&per-page=【篇數】
```

- 期刊一律用 ISSN 指定，不用刊名：刊名會撞名（OpenAlex 用 `journal of finance` 搜刊名會搜到 447 本）。
- `is_core:true` 只留核心期刊，排除冒名期刊。
- `title_and_abstract.search` 只比對標題與摘要，不比全文，免得撈進一堆不相關的論文。

## 失敗怎麼辦
- 程式說 `429` 或額度用完：停下來告訴使用者。
- 程式說「對照表裡沒有這本」：走「新增期刊」，不可以自己猜 ISSN、不可以自己組網址繞過去。
- 程式其他錯誤：看訊息修正指令再跑，最多 3 次；還是不行就把錯誤訊息貼給使用者。
- 檢查沒過（檔案不在、列數不對）：重跑一次程式再檢查。
