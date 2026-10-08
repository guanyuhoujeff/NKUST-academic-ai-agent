# 與 AI Agent 一起做學術工作：課堂工具包

這是高科大講座「**你的第一個 AI 研究助理，今天上工：與 AI Agent 一起做學術工作**」的上課教材。

把這個資料夾下載下來、用 OpenCode 打開，你就有一個會幫你**找文獻、讀文獻、寫文獻回顧、做簡報**的 AI 助理。

> 這堂課最重要的一句話：**AI 說它做完了，你要驗的是它做出來的東西，不是它說的話。**

---

## 一、下載

1. 按這一頁上方綠色的 **Code** → **Download ZIP**
2. 解壓縮到**你自己規劃的工作資料夾**（放哪裡、取什麼名字由你決定）
3. 打開看看，裡面要有 `AGENTS.md` 和 `.opencode` 資料夾（`.opencode` 開頭有一個點，Mac 要按 `Cmd + Shift + .` 才看得到）


---

## 二、課前準備（請在家先做好）

| 要準備的 | 怎麼做 | 用在哪 |
|---|---|---|
| **OpenCode 桌面版** | 到 OpenCode 官網下載安裝 | 跟 AI 講話的視窗 |
| **Ollama 帳號與 key** | 到 [ollama.com](https://ollama.com) 註冊 → 設定 → API keys → 建立 → 複製 | 提供免費的 AI 模型 |
| **OpenAlex key** | 到 [openalex.org/settings/api](https://openalex.org/settings/api) 免費申請，不用信用卡 | 找文獻 |
| **一個 Google 帳號** | 建議另外開一個專門給 AI 用的，不要用平常收信那個 | 分析文獻（NotebookLM） |

### 在 OpenCode 接上模型

1. OpenCode 設定 → 模型供應商 → **Ollama Cloud** → 貼上你的 Ollama key
2. 🔴 **一定要把模型換成 `gpt-oss:120b`**。預設的模型不在免費方案裡，用了會失敗。
   - 很慢或出錯時，備用：`gemma4:31b`、`nemotron-3-ultra`
3. 用 OpenCode **開啟你的工作資料夾**

### Python 和 nlm：叫 AI 幫你裝

在 OpenCode 輸入：

```
請檢查我的電腦有沒有 Python 3.11 以上，然後幫我安裝 nlm：套件名稱是 notebooklm-mcp-cli（https://pypi.org/project/notebooklm-mcp-cli/），裝完執行 nlm --version 確認
```

> 一定要講出套件名稱。`nlm` 只是指令的名字，只說「nlm」的話，AI 會去裝一個不存在的 `nlm` 套件然後失敗。

它會自己檢查、自己安裝。有兩件事要你自己來：

- 電腦**完全沒有 Python**：到 [python.org](https://www.python.org/downloads/) 下載安裝（Windows 安裝時要勾選 **Add python.exe to PATH**），裝完重開 OpenCode
- 它叫你**登入 Google**（`nlm login`）時：自己在瀏覽器登入，它不能替你輸入密碼

---

## 三、四個工具（skill）怎麼用

在 OpenCode 裡**直接用中文跟它說**就好。每個工具都會在重要的地方停下來問你，你確認了才會往下做。

| 工具 | 跟它說 | 你會拿到 |
|---|---|---|
| **找文獻** `fetch-literature` | 用 fetch-literature 找 The Journal of Finance 2015 年以後，option pricing 的論文 | `literature.md`：附 DOI 的文獻清單 |
| **分析文獻** `analyze-literature` | 用 analyze-literature 分析 papers/ 裡的論文<br>（先把 PDF 放進 `papers` 資料夾） | `notes/` 裡每篇一張**文獻卡**，每一點都標了原文頁碼 |
| **寫文獻回顧** `write-review` | 用 write-review 幫我寫文獻回顧，讀者是金融系大三學生 | `screening.md`（每篇相關或不相關＋理由）、`review.md`（每一句都有出處的文獻回顧，參考文獻由程式產生） |
| **做簡報** `make-slides` | 用 make-slides 把文獻卡做成 8 分鐘的報告 | `slides.pptx`：可以用 PowerPoint 打開修改 |
| **一次跑完** `lit-pipeline` | 用 lit-pipeline 幫我做選擇權定價的文獻報告 | 依序跑完上面四步 |

### 找你自己領域的期刊

找文獻的工具內建 8 本選擇權相關期刊。要查別的期刊：

1. 到國科會「[各學門審查參考原則](https://www.nstc.gov.tw/hum/ch/detail/da71f59b-9ab8-41f4-ae93-5973e0701cc7)」找你的學門；財金是「**財金及會計**」，它的審查參考原則 PDF 附有期刊分級報告（例如[財務領域國際期刊分級排序](https://www.nstc.gov.tw/nstc/attachments/00b9d9bb-2bf8-4e02-822a-8e48eee82404)）
2. 挑幾本期刊，跟 OpenCode 說：

```
請把 Journal of Banking and Finance、Journal of Corporate Finance 加進期刊對照表，等級是國科會 A Tier-1
```

它會用程式到 OpenAlex 查 ISSN；遇到**同名期刊會停下來問你選哪一本**，等級也只照你說的寫。

### write-review 需要多做一步

寫文獻回顧時，「逐篇初篩」是由程式一篇一篇直接問模型（避免 AI 偷懶），所以程式要拿得到你的 Ollama key。請擇一：

- 在工作資料夾裡建一個檔案 `.ollama_key`，內容只有你的 Ollama key 一行；或
- 把 key 設成環境變數 `OLLAMA_API_KEY`，再重開 OpenCode

> 🔒 **不要把 key 貼到對話裡，也不要上傳到 GitHub。** 這個資料夾的 `.gitignore` 已經排除 `.ollama_key`。

---

## 四、資料夾裡有什麼

```
你的工作資料夾/
├── AGENTS.md            AI 的工作守則（每次開工都會先讀）
├── .opencode/
│   ├── skills/          四個工具，每個都是「說明書 SKILL.md ＋ 檢查程式 scripts/」
│   │   ├── fetch-literature/     找文獻
│   │   ├── analyze-literature/   分析文獻
│   │   ├── write-review/         寫文獻回顧
│   │   └── make-slides/          做簡報
│   └── agents/
│       └── lit-pipeline.md       四步一次跑完
├── papers/              放你要分析的 PDF
├── notes/               文獻卡會產生在這裡
└── sources/             其他想給簡報用的資料（.md）
```

想知道 AI 被要求怎麼做事，打開 `AGENTS.md` 和各個 `SKILL.md` 看，都是中文寫的。

---

## 五、驗收：每一步都要自己看一眼

| 做完 | 怎麼驗 |
|---|---|
| 找文獻 | 隨便點一個 DOI，看是不是真的有這篇，作者、年份、期刊對不對 |
| 分析文獻 | 抽文獻卡上的一點，照它標的頁碼翻到 PDF 那一頁，看原文是不是真的這樣寫 |
| 寫文獻回顧 | 程式已經檢查過出處、頁碼、數字；**一句話的意思有沒有被寫歪，要你自己對照文獻卡讀** |
| 做簡報 | 打開 pptx，看每一頁的數字和來源是不是對得上 |

---

## 六、常見問題

| 狀況 | 原因與解法 |
|---|---|
| 出現 `usage limit` | Ollama 免費帳號每個月有用量上限，不是你做錯。等下個月，或換一個帳號的 key |
| 模型一直沒反應或出錯 | 確認模型是 `gpt-oss:120b`；不行就換 `gemma4:31b` |
| AI 說「已經完成」，但找不到檔案 | 這就是為什麼要驗收。請它「列出產出檔案的完整路徑」，再自己打開檔案總管確認 |
| Windows 上 `python` 指令無效 | 改用 `py` |
| 裝好 nlm 卻說找不到指令 | 請 AI 改用 `python -m notebooklm_tools.cli.main` |
| 找不到 `.opencode` 資料夾 | 它是隱藏資料夾；Mac 按 `Cmd + Shift + .`，Windows 在檔案總管「檢視」勾選「隱藏的項目」 |
