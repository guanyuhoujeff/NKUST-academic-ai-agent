---
name: fetch-literature
description: 找學術文獻時使用。向 OpenAlex 查詢指定期刊、指定主題的論文，產出附 DOI 的文獻清單 literature.md。
---

# 抓文獻

向 OpenAlex（免費公開的學術資料庫）查論文，交出一份每一筆都查得到的文獻清單。

## 步驟

### 0. 確認 OpenAlex 金鑰
查詢要帶金鑰，否則會和同一個網路上的所有人共用一個很小的額度。金鑰放在環境變數 `OPENALEX_API_KEY`。

1. 用 Shell 工具查環境變數有沒有值（Windows PowerShell 用 `echo $env:OPENALEX_API_KEY`；macOS／Linux 用 `echo $OPENALEX_API_KEY`）。
2. **有值**：直接用，不用再問。
3. **沒有值**：停下來請使用者提供金鑰，並附上申請網址 https://openalex.org/settings/api （免費，不用信用卡）。在使用者給金鑰之前不要往下做，也不要用沒有金鑰的網址查詢。
4. 使用者在對話中給了金鑰之後，**收到金鑰的第一個動作**是用 Shell 工具執行下面這行，把金鑰存起來讓下次不用再問；**做完這行才可以開始查詢**：
   - macOS／Linux：`echo 'export OPENALEX_API_KEY="金鑰"' >> ~/.bashrc`
   - Windows：`setx OPENALEX_API_KEY "金鑰"`
   然後告訴使用者「金鑰已存入環境變數，重開 OpenCode 後生效；本次先直接用這把金鑰繼續」。

### 1. 確認三件事
- **主題關鍵字**：用英文，例如 `option pricing`。
- **期刊**：使用者指定的期刊。
- **起始年**：使用者沒說就用 2015。

### 2. 把刊名換成 ISSN
讀 `references/journals.md`，找到該期刊的 ISSN。

**期刊一律用 ISSN 指定，不可以用刊名搜尋。** 刊名只是一串字，會撞名：在 OpenAlex 用 `journal of finance` 搜刊名會搜到 447 本不同的期刊。ISSN 是國際標準編號，一本期刊一個。

清單裡沒有這本期刊時，停下來告訴使用者「清單裡沒有，請提供 ISSN」，不要自己猜。

### 3. 組出查詢網址
把步驟 0 取得的金鑰和前面確認的條件，照這個樣板填入：

```
https://api.openalex.org/works?filter=primary_location.source.issn:【ISSN】,primary_location.source.is_core:true,title_and_abstract.search:%22【關鍵字】%22,from_publication_date:【起始年】-01-01&sort=cited_by_count:desc&per-page=10&select=doi,title,publication_year,cited_by_count,authorships,primary_location&api_key=【金鑰】
```

- 關鍵字裡的空白要換成 `%20`，例如 `option%20pricing`。
- `is_core:true` 只留核心期刊，用來排除冒名期刊。
- `title_and_abstract.search` 只比對標題與摘要。不要改成 `default.search`，那會連全文一起比對，撈進一堆不相關的論文。

### 4. 送出查詢
用 webfetch 工具抓這個網址（格式選 text）。webfetch 失敗就改用 `curl -s "網址"`。

回傳的 `meta.count` 是符合條件的總筆數，`results` 是論文清單。

### 5. 寫成 literature.md
在工作資料夾寫出 `literature.md`（用相對路徑 `literature.md`，**不可以寫到 `/tmp` 或其他資料夾**），內容：

1. 標題與一行查詢條件（主題、期刊與 ISSN、起始年、總筆數、查詢日期）。
2. 一張表格，每篇論文一列，欄位依序為：年份｜作者｜標題｜期刊｜被引數｜DOI。
   - 作者取 `authorships` 裡每個人的 `author.display_name`，超過三位就寫前三位加「等」。
   - 標題、作者、DOI **照回傳內容原樣抄寫**，不可改寫、不可翻譯、不可補上回傳內容裡沒有的論文。
3. 表格下方附上實際送出的查詢網址，但要把金鑰換成 `***`。

查詢結果是 0 筆時，照實寫「0 筆」，不要自己補論文。

## 檢查（交出去之前一定要做）

1. 列出工作資料夾的檔案，確認 `literature.md` 就在裡面；再讀回來，確認表格列數等於回傳的論文數。
2. 確認每一列的 DOI 都以 `https://doi.org/` 開頭。
3. 確認每一列的期刊都是使用者指定的那一本。
4. 確認檔案裡沒有出現金鑰。
5. 如果金鑰是使用者這次在對話中提供的，確認已經照步驟 0 寫進環境變數；還沒寫就現在補寫。

## 失敗怎麼辦

- 回傳 `429` 或提到 budget：今天的額度用完了，停下來告訴使用者。
- 回傳其他錯誤：檢查網址有沒有照樣板、空白有沒有換成 `%20`，修正後重試，最多 3 次。
- 任何一項檢查沒過：修正 `literature.md` 後重新檢查。
