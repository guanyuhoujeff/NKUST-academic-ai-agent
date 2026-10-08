#!/usr/bin/env python3
"""做簡報的流程管家：告訴你現在該做哪一步，並守住每一關。
用法（都在工作資料夾執行）:
  python slides.py next                 現在該做什麼？（每一輪對話的第一個動作）
  python slides.py angle "選定的主軸"    使用者選好主軸（講法）之後執行
  python slides.py check-outline        檢查 outline.md
  python slides.py approve              使用者同意大綱之後執行
  python slides.py theme <代號> [--page-by-page]
                                        使用者選好風格之後執行；他說要一頁一頁討論才加 --page-by-page
  python slides.py page-ok              （逐頁模式）使用者同意目前這一頁之後執行
  python slides.py pages-off            （逐頁模式）使用者說「剩下的你直接做完」時執行
  python slides.py build                產生 slides.pptx 並檢查
  python slides.py sources-ok           使用者確認新放進來源（literature.md、notes/、sources/）的檔案是他放的
  python slides.py auto "使用者原話" [代號]   使用者明說「全部交給你、不用問我」時執行，跳過所有停頓點
進度記在 .slides-state.json；大綱改過就要重新檢查、重新給使用者確認。
"""
import json, os, re, sys, hashlib, pathlib, unicodedata, subprocess, difflib

# Windows 繁中版主控台是 cp950：來源檔裡的「‐」「é」「💡」會讓 print 當掉，中文也會被 opencode 讀成亂碼。一律用 UTF-8 輸出。
for _stream in (sys.stdout, sys.stderr):
    try: _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build as B

ME = "python .opencode/skills/make-slides/scripts/slides.py"
STATE, OUTLINE, DECK = pathlib.Path(".slides-state.json"), pathlib.Path("outline.md"), pathlib.Path("deck.json")
ORDER = ["start", "angled", "checked", "approved", "themed", "built"]

def load():
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"stage": "start"}
    if OUTLINE.exists() and st.get("outline_hash") and st["outline_hash"] != digest():
        st = {"stage": "angled", "angle": st.get("angle", ""), "auto": st.get("auto", False), "sources": st.get("sources"),
              "note": "outline.md 改過了，要重新檢查、重新給使用者確認"}
    return st


def all_sources():
    """來源 = literature.md + notes/**/*.md（不含 README.md）+ sources/**/*.md"""
    found = [pathlib.Path("literature.md")] if pathlib.Path("literature.md").exists() else []
    for d in ("notes", "sources"):
        if pathlib.Path(d).exists(): found += [p for p in pathlib.Path(d).glob("**/*.md") if p.name != "README.md"]
    return sorted(found)

def manifest():
    return {str(p): hashlib.sha1(p.read_bytes()).hexdigest() for p in all_sources()}

def sources():
    """只認流程開始時就存在、且沒被改過的來源檔；新增或改過的要使用者確認（sources-ok）才算。"""
    allp = all_sources()
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    known = st.get("sources")
    if known is None: return allp
    return [p for p in allp if known.get(str(p)) == hashlib.sha1(p.read_bytes()).hexdigest()]

def unknown_sources():
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    known = st.get("sources")
    if known is None: return []
    return [str(p) for p in all_sources() if known.get(str(p)) != hashlib.sha1(p.read_bytes()).hexdigest()]

def save(st): STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
def digest(): return hashlib.sha1(OUTLINE.read_bytes()).hexdigest()
def at_least(st, stage): return ORDER.index(st["stage"]) >= ORDER.index(stage)
def norm(x):
    """比對引文時只看文字與數字：標點、空白、粗體記號、全形半形的差異都不算。"""
    return re.sub(r"[\W_]", "", unicodedata.normalize("NFKC", x)).lower()

def quoted_ok(q, blob):
    """引文中間用 … 省略時，每一段都要在來源裡找得到。"""
    parts = [norm(x) for x in re.split(r"…+|\.{3,}", q)]
    parts = [x for x in parts if len(x) >= 4]
    return bool(parts) and all(x in blob for x in parts)

def nearest(q, raw, blob):
    """在來源裡找和引文最像的一小段，回傳可以直接照抄、而且保證過得了檢查的文字（60 字以內）。"""
    grams = lambda s: {s[i:i + 2] for i in range(len(s) - 1)}
    target = grams(norm(q)); best, score = "", 0.0
    if not target: return ""
    for line in raw.splitlines():
        parts = [x.strip(" *-|>#\t") for x in re.split(r"[。；：:（）()]|(?<!\d)[，,]|[，,](?!\d)", line)]   # 不在數字的千分位逗號上切
        parts = [x for x in parts if x]
        for i in range(len(parts)):           # 單一子句，以及相鄰兩個子句合起來
            for cand in (parts[i], "，".join(parts[i:i + 2])):
                c = re.sub(r"^[\W_]+|[\W_]+$", "", cand.replace("*", ""))   # 去掉頭尾殘留的符號
                if not 6 <= len(norm(c)) or len(c) > 58: continue
                r = len(target & grams(norm(c))) / len(target)
                if r > score and quoted_ok(c, blob): best, score = c, r
    return best if score >= 0.3 else ""

# ---------- 大綱 ----------
def parse_outline():
    txt = OUTLINE.read_text(encoding="utf-8"); rows = []
    for ln in txt.splitlines():
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if ln.strip().startswith("|") and len(c) >= 4 and c[0].isdigit():
            rows.append(dict(n=int(c[0]), layout=c[1].strip("` "), title=c[2].strip("* "), evidence=" | ".join(c[3:])))
    return txt, rows

def simplified_in(text):
    """回傳 text 裡的簡體字（去重、照出現順序）；用 build.py 的同一份字表。"""
    seen = []
    for ch in text:
        if ch in B.SIMPLIFIED and ch not in seen: seen.append(ch)
    return seen

def check_outline():
    if not OUTLINE.exists():
        return ["找不到 outline.md"], []
    txt, rows = parse_outline(); bad = []
    for key in ("聽眾", "時間", "一句話"):
        if not re.search(key + r"[^\n：:]*[：:]\s*\S", txt):
            bad.append(f"開頭少了「{key}」那一行（格式：- {key}：內容）")
    if len(rows) < 3:
        bad.append("大綱表少於 3 頁，或表格格式不對（每列要是：| 頁碼 | 版面 | 標題 | 證據 |）")
        return bad, rows
    raw = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources())
    blob = norm(raw)
    run, prev = 0, None
    for r in rows:
        tag = f"第 {r['n']} 頁"
        if r["layout"] not in B.LAYOUTS:
            bad.append(f"{tag}的版面「{r['layout']}」不存在，可用的是 {' / '.join(B.LAYOUTS)}"); continue
        run = run + 1 if r["layout"] == prev else 1; prev = r["layout"]
        if run == B.MAX_SAME_LAYOUT + 1 and r["layout"] != "section":
            bad.append(f"{tag}起連續 {run} 頁都是 {r['layout']}，換一種版面或插一頁 section")
        if r["layout"] == "section" and run == B.MAX_SECTIONS + 1:
            bad.append(f"{tag}是連續第 {run} 頁 section（只有標題），太空了：把其中一頁改成 assertion，寫出要聽眾記住的事實")
        if (sc := simplified_in(r["title"])):
            bad.append(f"{tag}標題有簡體字：{'、'.join(sc)}。一律用台灣繁體中文")
        if B.GENERIC.match(r["title"]):
            bad.append(f"{tag}標題「{r['title']}」只是主題，請改成一句結論")
        if B.title_lines(r["title"], 10.55 if r["layout"] != "section" else 9.2, 34) > 2:
            bad.append(f"{tag}標題太長（投影片上會折成 3 行以上、壓到內容），請縮短到約 40 個中文字以內")
        ghost = B.not_in_source(r["title"], raw)
        if ghost:
            bad.append(f"{tag}標題裡的 {'、'.join(sorted(ghost))} 在來源檔裡找不到。標題的數字要和來源一模一樣，不可以自己估或換算")
        if r["layout"] == "section":
            continue
        quotes = [q for q in re.findall(r"「([^」]{4,})」", r["evidence"])]
        if not quotes:
            bad.append(f"{tag}的證據欄沒有引文。請從來源檔原樣抄一句，用「」括起來")
        elif max(len(q) for q in quotes) > 60:
            bad.append(f"{tag}的引文太長（{max(len(q) for q in quotes)} 字）。只抄最關鍵的一句，60 字以內")
        elif not any(quoted_ok(q, blob) for q in quotes):
            hint = nearest(quotes[0], raw, blob)
            bad.append(f"{tag}的引文在來源檔裡找不到：「{quotes[0][:30]}」。請回來源檔原樣抄，不可以改寫或自己編"
                       + (f"。來源裡最接近的一句是：「{hint}」——意思對的話可以直接照抄這句" if hint else "。來源裡沒有相近的句子，這一頁的說法可能不是來源講的，請換一個有依據的"))
    if len({r["layout"] for r in rows}) < 3:
        bad.append("整份只用了不到 3 種版面，請依內容換用 bignumber / table / compare / quote")
    return bad, rows

ANGLE_HOWTO = """## 現在要做的事：和使用者談主軸（這份簡報要怎麼講）

1. 用讀檔工具把下面每個來源檔【從頭讀到尾】（只搜尋關鍵字不算）：
{files}
   各檔的章節與重點行如下（這只是目錄，細節要讀原文）：
{digest}
2. 使用者還沒講的就問：聽眾是誰、講多久。已經講過的不用再問。
3. 根據來源，向使用者提出【2 到 3 個不同的主軸】讓他挑。每個主軸寫三行：
   - 一句話：聽眾聽完要記住什麼（使用者已經給了那一句話，就提 2–3 種不同的講法來撐它）
   - 怎麼講：大概的順序，例如「先講痛點 → 再講數字 → 最後講應用」
   - 會用到：來源裡的哪些材料
   主軸之間要真的不一樣（例如一個從速度切入、一個從應用切入），不要只是換句話說。
4. 問使用者：選哪一個？或是他有自己的想法？然後【這一輪到此結束】，等他回覆。不要寫 outline.md。

使用者選好之後執行（把他選的主軸用一兩句話寫進引號裡）：
{me} angle "一句話：…；講法：…"
"""

OUTLINE_HOWTO = """## 現在要做的事：寫大綱 outline.md

使用者選定的主軸：{angle}

1. 來源檔在這裡，寫大綱時要回去查原文：
{files}
2. 照使用者選的主軸安排每一頁，不要自己換成別的講法。
3. 在工作資料夾寫出檔案 outline.md，格式照抄這個樣子：

# 簡報大綱

- 聽眾：（誰、已經知道什麼）
- 時間：（幾分鐘）
- 要對方記住的一句話：（一句）
- 風格：（先留空）

| 頁 | 版面 | 標題（一句結論） | 證據（從來源原樣抄一句，用「」括起來，後面註明哪個檔） |
|---|---|---|---|
| 1 | section | 開場的一句話 | — |
| 2 | bignumber | 這一頁的結論句 | 「從來源檔原樣抄的一句話」（某某.md） |

規則：
- 大約一分鐘一頁。
- 版面只能用：section（換段落／開場／結尾）、assertion（結論＋證據）、bignumber（一個大數字）、table（多筆並排）、compare（兩欄對照）、quote（引言）。至少用三種，同一種不要連續超過 3 頁。
- 標題是一句結論，不是主題。「深度學習簡介」是主題；「神經網路把定價從幾十萬微秒縮短到幾十微秒」是結論。
- 除了 section 以外，每一頁的證據欄都要有一句從來源檔【原樣抄下來】的話（60 字以內），用「」括起來。程式會去來源檔裡找這句話，找不到就不會過。\n- 標題要是那句引文撐得起來的結論。標題裡的數字必須和來源一模一樣，不可以自己估算（來源寫 0.5% 就不能寫成「近 30%」）。
- 結尾頁用 section 版面。

4. 寫完後執行：{me} check-outline
"""

THEMES_TEXT = """## 現在要做的事：請使用者選風格，並問他要不要逐頁討論

一次問這兩件事，然後【這一輪到此結束】，等他回覆。

（一）風格：把下面三套介紹給使用者，依他的聽眾與場合【推薦一個並說明理由】，請他選。
- academic 學術簡潔：白底、深藍標題、一道紅色短線。安靜、不搶內容。適合課堂報告、口試。
- editorial 編輯雜誌：米色底、黑色大標題、左側磚紅色直條。像財經雜誌內頁。適合讀書會分享。
- stage 深色講台：深藍黑底、白字、琥珀色強調，字最大。適合大教室、投影機偏暗。

（二）製作方式：問他「每一頁的內容要不要一頁一頁跟你確認？還是我整份做好再給你看？」
- 預設是整份做好再給他看。使用者沒有明確說要逐頁，就不要逐頁。

使用者回覆之後執行其中一行（代號只能是 academic、editorial、stage）：
- 整份做好再給他看（預設）：{me} theme <代號>
- 他明確說要一頁一頁討論：{me} theme <代號> --page-by-page
"""

PAGE_HOWTO = """## 現在要做的事：和使用者討論第 {i} 頁（共 {n} 頁）

大綱上這一頁是：版面 {layout}｜標題「{title}」
{head}
1. 回來源檔找這一頁要用的材料，把這一頁寫進 deck.json 的 slides（第 {i} 個）。layout 和 title 照大綱一字不差。
   各版面要有的欄位：assertion→bullets；bignumber→number、caption、bullets；table→table；
   compare→left 與 right（各有 heading、bullets）；quote→quote、by；section→可加 kicker、subtitle（章節頁不顯示要點，不要寫 bullets）。
   每頁最多 5 條要點，每條最多 45 個字；數字從來源原樣抄；來源沒寫的不可以出現。
   每條要點盡量帶一個具體事實（數字、年份、樣本數、倍數、方法或作者名稱），不要寫「效果顯著」「表現優異」這種形容。
   可加 "icon"（右上角的圖示）：{icons}；不寫會依標題自動挑，寫 none 就不放。
2. 用【人看得懂的樣子】把這一頁貼給使用者（標題＋要點或表格，不要貼 JSON），問他：這頁可以嗎？要加什麼、刪什麼、換個說法？
3. 【這一輪到此結束】，等他回覆。不要先做下一頁。

使用者回覆之後：
- 他說可以 → 執行：{me} page-ok
- 他要改 → 改 deck.json 的這一頁，再貼給他看一次
- 他說「剩下的你直接做完」→ 執行：{me} pages-off
"""

DECK_HOWTO = """## 現在要做的事：寫 deck.json，然後產生簡報

依照 outline.md，在工作資料夾寫出 deck.json。每一頁的 layout 和 title 要和大綱【一字不差】。格式：

{{"title": "封面標題", "subtitle": "副標題", "theme": "{theme}",
 "sources": [{srcs}],
 "slides": [
  {{"layout": "section", "kicker": "第一部分", "title": "…"}},
  {{"layout": "assertion", "title": "…", "icon": "growth", "bullets": ["…", "…"], "note": "資料來源：…"}},
  {{"layout": "bignumber", "title": "…", "number": "11", "caption": "這個數字是什麼", "bullets": ["…"]}},
  {{"layout": "table", "title": "…", "table": [["欄名A", "欄名B"], ["值", "值"]]}},
  {{"layout": "compare", "title": "…", "left": {{"heading": "…", "bullets": ["…"]}}, "right": {{"heading": "…", "bullets": ["…"]}}}},
  {{"layout": "quote", "title": "…", "quote": "從來源原樣抄的一句", "by": "出處"}}
 ]}}

規則：
- 數字、年份、作者、刊名、DOI 從來源檔原樣抄，不可以換算、四捨五入或自己補。
- 每頁最多 5 條要點，每條最多 45 個字。要點是你【濃縮過】的短句，不要把大綱裡的引文整句貼上來。
- 【每條要點都要有一個具體事實】：數字、年份、樣本數、倍數、方法或作者名稱，從來源原樣抄。「預測精度提升」「適用多種市場」這種沒有事實的形容會被 build 擋下來。
- 【每頁挑一個圖示】放在 "icon"：{icons}。挑最貼近這頁意思的（加速→speed、資料→data、風險→warning、提問→question）；不寫會依標題自動挑，寫 none 就不放。
- 標題最多兩行（約 40 個中文字），太長會壓到內容。
- section（章節頁）只顯示標題，不要在上面寫 bullets；結尾的「小結」要列出重點的話，用 assertion。
- 內容只能來自來源檔（literature.md、notes/、sources/）。來源沒寫的案例、模型名稱、結論，一律不可以出現。

寫完後執行：{me} build
"""

def digest_sources():
    """每個來源檔的章節標題與重點行，讓你在讀全文之前先看到全貌。"""
    out = []
    for p in sources():
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        heads = [l.strip() for l in lines if re.match(r"^\s*(#{1,4}\s|\*\s+\*\*|\d+\.\s+\*\*|\|\s*\d{4}\s*\|)", l)]
        out.append(f"### {p}\n" + "\n".join("  " + h[:110] for h in heads[:14]))
    return "\n".join(out)

def file_list():
    return "\n".join(f"   - {p}（{len(p.read_text(encoding='utf-8', errors='replace'))} 字）" for p in sources())

def src_list(): return ", ".join(f'"{p}"' for p in sources())

def deck_howto(st):
    return DECK_HOWTO.format(theme=st["theme"], srcs=src_list(), me=ME, icons=" / ".join(B.ICONS))

def page_howto(st):
    _, rows = parse_outline(); i = st["page"]; r = rows[i - 1]
    head = ""
    if i == 1:
        head = ("\n這是第一頁，先建立 deck.json 的外框：\n"
                f'{{"title": "封面標題", "subtitle": "副標題", "theme": "{st["theme"]}", "sources": [{src_list()}], "slides": []}}\n')
    return PAGE_HOWTO.format(i=i, n=len(rows), layout=r["layout"], title=r["title"], head=head, me=ME, icons=" / ".join(B.ICONS))

def warn_unknown():
    u = unknown_sources()
    if u:
        print("注意：來源裡有流程開始後才出現或被改過的檔案，程式不會採用它們：" + "、".join(u))
        print("  來源檔只能由使用者放進來。如果是你建立或改寫的，立刻刪掉——自己寫來源等於編造證據。")
        print(f"  如果是使用者放的，請他確認後執行：{ME} sources-ok\n")

def cmd_next(st):
    if st.get("note"): print("注意：" + st["note"] + "\n")
    if st.get("sources") is None:
        st["sources"] = manifest(); save(st)
    warn_unknown()
    if not sources():
        print("找不到任何來源檔（literature.md、notes/*.md、sources/*.md 都沒有）。停下來告訴使用者：請先用 fetch-literature 產出 literature.md、用 analyze-literature 產出 notes/，或把自己的 .md 放進 sources/，放好之後再叫你繼續。"
              "\n不要自己建立來源檔。"); return
    if not at_least(st, "angled"):
        print(ANGLE_HOWTO.format(files=file_list(), me=ME, digest=digest_sources())); return
    if not OUTLINE.exists():
        print(OUTLINE_HOWTO.format(files=file_list(), me=ME, angle=st.get("angle") or "（由你決定）")); return
    if not at_least(st, "checked"):
        print(f"outline.md 已經有了，但還沒通過檢查。執行：{ME} check-outline"); return
    if not at_least(st, "approved"):
        print("大綱已通過檢查，正在等使用者確認。\n"
              "- 使用者還沒看過 → 把 outline.md 的大綱表原樣貼給他，問他要不要改，然後【這一輪到此結束】。\n"
              f"- 使用者已經說可以 → 現在就執行：{ME} approve（它會告訴你下一步）\n"
              "- 使用者要改 → 照他說的改 outline.md，再執行 check-outline，通過後再貼給他看一次。"); return
    if not at_least(st, "themed"):
        print(THEMES_TEXT.format(me=ME)); return
    if not at_least(st, "built"):
        print(page_howto(st) if st.get("page_mode") else deck_howto(st)); return
    print("簡報已經做好並通過檢查。把上一次 build 印出的檢查結果原樣貼給使用者，列出每頁的版面與標題。\n"
          f"使用者要改內容 → 改 deck.json 再執行 {ME} build；要改大綱 → 改 outline.md 再執行 check-outline。")

def cmd_sources_ok(st):
    u = unknown_sources()
    if not u: print("來源裡沒有待確認的檔案。"); return
    st["sources"] = manifest(); save(st)
    print("已記錄：使用者確認這些是他放的來源檔：" + "、".join(u) + f"\n接著執行：{ME} next")

def cmd_angle(st, text):
    if not text.strip():
        sys.exit(f'要把使用者選的主軸寫進引號裡，例如：{ME} angle "一句話：…；講法：…"')
    if (sc := simplified_in(text)):
        sys.exit(f"主軸裡有簡體字：{'、'.join(sc)}。改成台灣繁體中文再執行一次 angle")
    if at_least(st, "checked"):
        print("注意：大綱已經寫好了。改主軸之後，outline.md 要照新的主軸重寫並重新檢查。")
    save({"stage": "angled", "angle": text.strip(), "auto": st.get("auto", False), "sources": st.get("sources")})
    print(f"已記錄主軸：{text.strip()}\n")
    print("【不要停下來】這一輪就接著做下面的事：寫 outline.md → 執行 check-outline → 把大綱貼給使用者。\n")
    print(OUTLINE_HOWTO.format(files=file_list(), me=ME, angle=text.strip()))

def cmd_check(st):
    warn_unknown()
    if not at_least(st, "angled"):
        sys.exit(f"還不能檢查大綱：還沒和使用者談定主軸。執行：{ME} next")
    bad, rows = check_outline()
    if bad:
        print(f"OUTLINE 未通過，有 {len(bad)} 個問題：")
        for b in bad: print("  - " + b)
        print(f"\n修改 outline.md 後再執行：{ME} check-outline"); sys.exit(2)
    new = {"stage": "checked", "outline_hash": digest(), "angle": st.get("angle", ""), "auto": st.get("auto", False), "sources": st.get("sources")}
    print(f"OUTLINE OK：共 {len(rows)} 頁，每一頁的引文都在來源檔裡找到了。\n")
    if new["auto"]:
        new.update(stage="themed", theme=st.get("theme") or "academic"); save(new)
        print(f"（使用者把決定交給你）風格採用 {new['theme']}，直接製作。最後回報時要附上完整大綱表。\n"); print(deck_howto(new)); return
    save(new)
    print("現在把下面這張大綱表【原樣貼給使用者】，問他：頁數要增減嗎？哪一頁的說法要改？有沒有漏掉想講的？")
    print("然後【這一輪到此結束】。不要寫 deck.json，不要執行 build。\n")
    print("| 頁 | 版面 | 標題 |\n|---|---|---|")
    for r in rows: print(f"| {r['n']} | {r['layout']} | {r['title']} |")
    print(f"\n使用者說可以之後執行：{ME} approve")

def cmd_approve(st):
    if not at_least(st, "checked"):
        sys.exit(f"還不能確認：大綱沒有通過檢查。執行：{ME} check-outline")
    st["stage"] = "approved"; st.pop("note", None); save(st)
    print("已記錄：使用者同意這份大綱。\n"); print(THEMES_TEXT.format(me=ME))

def cmd_theme(st, args):
    name = next((a for a in args if not a.startswith("--")), "")
    if not at_least(st, "approved"):
        sys.exit("還不能選風格：程式還沒記錄「使用者同意大綱」。\n"
                 f"- 使用者已經說大綱可以 → 依序執行這兩行：\n    {ME} approve\n    {ME} theme {name}\n"
                 "- 使用者還沒看過大綱 → 先把大綱貼給他確認。")
    if name not in B.THEMES:
        sys.exit(f"沒有「{name}」這個風格，可用的是 {' / '.join(B.THEMES)}")
    st.update(stage="themed", theme=name, page_mode="--page-by-page" in args, page=1); save(st)
    print(f"已記錄風格：{name}（{B.THEMES[name]['name']}）；製作方式：{'一頁一頁和使用者討論' if st['page_mode'] else '直接做完整份'}。\n")
    print(page_howto(st) if st["page_mode"] else deck_howto(st))

def load_deck():
    if not DECK.exists(): sys.exit(f"找不到 deck.json。執行：{ME} next 看怎麼寫")
    try: return json.loads(DECK.read_text(encoding="utf-8"))
    except Exception as e: sys.exit(f"deck.json 的 JSON 格式有錯：{e}")

def cmd_page_ok(st):
    warn_unknown()
    if not (st.get("page_mode") and st["stage"] == "themed"):
        sys.exit(f"現在不是逐頁討論模式。執行：{ME} next")
    _, rows = parse_outline(); i = st["page"]; deck = load_deck(); slides = deck.get("slides") or []
    if len(slides) < i:
        sys.exit(f"deck.json 裡還沒有第 {i} 頁。先把這一頁寫進去、貼給使用者看，他同意後再執行 page-ok。")
    sl = slides[i - 1]; bad = []
    if norm(sl.get("title", "")) != norm(rows[i - 1]["title"]):
        bad.append(f"標題和大綱不一樣（大綱是「{rows[i - 1]['title']}」）")
    err = B.validate({"title": "x", "theme": st["theme"], "slides": [sl]})
    if err: bad.append(err.replace("第 1 頁", "這一頁"))
    raw = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources())
    ghost = set().union(*[B.not_in_source(x, raw) for x in B.slide_texts(sl)] or [set()])
    if ghost: bad.append(f"{'、'.join(sorted(ghost))} 在來源檔裡找不到")
    bad += [w.replace("第 1 頁", "這一頁") for w in B.check_size({"slides": [sl]}) if "連續" not in w]
    if bad:
        print(f"第 {i} 頁還不能過：" + "；".join(bad) + f"\n修改 deck.json 的這一頁，再貼給使用者看；他同意後執行：{ME} page-ok"); sys.exit(2)
    if i >= len(rows):
        st["page_mode"] = False; save(st)
        print(f"第 {i} 頁已確認。所有頁面都和使用者談完了。\n現在執行：{ME} build"); return
    st["page"] = i + 1; save(st)
    print(f"第 {i} 頁已確認。\n"); print(page_howto(st))

def cmd_pages_off(st):
    if st["stage"] != "themed": sys.exit(f"現在不能切換。執行：{ME} next")
    done = st.get("page", 1) - 1; st["page_mode"] = False; save(st)
    print(f"已改成直接做完：前 {done} 頁維持使用者確認過的內容不要動，把剩下的頁面補進 deck.json。\n"); print(deck_howto(st))

def cmd_build(st):
    warn_unknown()
    if not at_least(st, "themed"):
        sys.exit("還不能產生簡報：" + ("使用者還沒選風格。" if at_least(st, "approved") else "大綱還沒寫好、檢查並給使用者確認。") + f" 執行：{ME} next")
    if st.get("page_mode"):
        sys.exit(f"還不能產生簡報：逐頁討論進行到第 {st['page']} 頁，還沒談完。執行：{ME} next")
    deck = load_deck()
    if not deck.get("sources"):   # 模型常忘了填 sources；程式知道來源是哪些，直接補上
        deck["sources"] = [str(p) for p in sources()]
        DECK.write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已自動補上 deck.json 的 sources：" + "、".join(deck["sources"]) + "\n")
    if deck.get("theme") != st["theme"]:
        sys.exit(f"BUILD FAILED: deck.json 的 theme 是「{deck.get('theme')}」，但使用者選的是「{st['theme']}」。請改成 {st['theme']}。")
    r = subprocess.run([sys.executable, str(HERE / "build.py"), "deck.json", "slides.pptx", "--pdf"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    print((r.stdout + r.stderr).strip())
    lines = [l for l in r.stdout.splitlines() if l.startswith("[") and not l.startswith("[預覽]")]
    ok = r.returncode == 0 and all(("通過" in l) or (l.startswith("[字型]") and "←" not in l) for l in lines)
    if ok:
        st["stage"] = "built"; save(st)
        print("\n全部通過。把上面幾行【原樣貼給使用者】，並列出每頁的版面與標題。")
    else:
        print(f"\n還有沒通過的檢查。修改 deck.json 後再執行：{ME} build\n（如果要改的是標題或頁數，那是改大綱：改 outline.md → check-outline → 再給使用者確認。）")
        sys.exit(2)

AUTO_WORDS = ("不用問", "不用确认", "不用確認", "全部交給", "都交給", "你決定", "你决定", "自己決定", "自動流程", "沒有人可以問")

def cmd_auto(st, args):
    said = " ".join(a for a in args if a not in B.THEMES and not a.startswith("--")).strip()
    if not any(w in said for w in AUTO_WORDS):
        sys.exit("auto 只能在使用者明說「全部交給你、不用問我」時使用，而且要把他的原話附在後面，例如：\n"
                 f'  {ME} auto "全部交給你，不用問我"\n'
                 "他只是選了風格、或說「整份做好再給我看」，都不算。那種情況請回到 next 照流程走。")
    name = next((a for a in args if a in B.THEMES), st.get("theme") or "academic")
    st["auto"] = True
    print("已記錄：使用者把所有決定交給你、不用問他（只有他明說「全部交給你」「不用問我」才可以這樣做；")
    print("他只是選了風格、或說「整份做好再給我看」，都【不算】——那種情況請改用 theme 指令）。")
    print(f"主軸由你決定，風格採用 {name}，不逐頁討論。最後回報時要附上完整大綱表，並說明哪些是你替他決定的。\n")
    if at_least(st, "checked"):
        st.update(stage="themed", theme=name, page_mode=False); save(st); print(deck_howto(st)); return
    st["stage"] = "angled"; st["theme"] = name; st.setdefault("angle", "（使用者交給你決定：選一個最能撐起核心訊息的講法）"); save(st)
    print("先讀完每個來源檔，再照下面的說明寫大綱。\n"); print(OUTLINE_HOWTO.format(files=file_list(), me=ME, angle=st["angle"]))

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "next"; st = load(); rest = sys.argv[2:]
    if cmd == "next": cmd_next(st)
    elif cmd == "angle": cmd_angle(st, " ".join(rest))
    elif cmd == "sources-ok": cmd_sources_ok(st)
    elif cmd == "check-outline": cmd_check(st)
    elif cmd == "approve": cmd_approve(st)
    elif cmd == "theme": cmd_theme(st, rest)
    elif cmd == "page-ok": cmd_page_ok(st)
    elif cmd == "pages-off": cmd_pages_off(st)
    elif cmd == "build": cmd_build(st)
    elif cmd == "auto": cmd_auto(st, rest)
    else: sys.exit(__doc__)

if __name__ == "__main__":
    main()
