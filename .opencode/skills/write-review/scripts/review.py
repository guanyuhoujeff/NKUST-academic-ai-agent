#!/usr/bin/env python3
"""寫文獻回顧的流程管家：記住做到哪一關、告訴模型下一步、檢查每一句都有出處。

  python review.py next                  每一輪第一個動作：印出現在在哪一關、要做什麼
  python review.py question "研究問題"     記下研究問題，開始逐篇初篩
  python review.py screen                初篩：程式一篇一篇問模型相關或不相關（分批跑，印「還有 N 篇」就再跑）
  python review.py include 檔名 "理由"     使用者要撈回某篇；exclude 是剔除
  python review.py show 檔名              印出一張文獻卡的本文（不含很長的附錄），第二輪讀卡用
  python review.py check-plan            檢查 plan.md（研究問題＋分節架構）
  python review.py approve               使用者看過（初篩結果或分節架構）、說可以之後執行
  python review.py check                 檢查 review.md；全部通過就自動補上參考文獻
  python review.py auto "使用者原話"      使用者明說「全部交給你、不用問我」時執行，跳過停頓點
進度記在 .review-state.json；初篩紀錄寫在 screening.md；plan.md 改過就要重新檢查、重新給使用者確認。
"""
import json, re, sys, time, hashlib, pathlib, unicodedata

for _s in (sys.stdout, sys.stderr):   # Windows 的主控台是 cp950，不改成 UTF-8 會當掉或變亂碼
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from zh_check import simplified_in
import screen

ME = "python .opencode/skills/write-review/scripts/review.py"
STATE, PLAN, REVIEW, NOTES, SCREEN = (pathlib.Path(p) for p in
                                      (".review-state.json", "plan.md", "review.md", "notes", "screening.md"))
ORDER = ["start", "screening", "screened", "planning", "planned", "approved", "done"]
AUTO_WORDS = ("不用問", "不用確認", "全部交給", "都交給", "你決定", "自己決定", "自動流程", "沒有人可以問")
GAP = "缺口"
YES, NO = "相關", "不相關"

# ---------- 狀態 ----------
def load():
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"stage": "start"}
    if at_least(st, "planned") and PLAN.exists() and st.get("plan_hash") != digest(PLAN):
        st = {**st, "stage": "planning", "note": "plan.md 改過了，要重新檢查、重新給使用者確認"}
    return st

def save(st): STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
def digest(p): return hashlib.sha1(p.read_bytes()).hexdigest()
def at_least(st, stage): return ORDER.index(st["stage"]) >= ORDER.index(stage)

# ---------- 文獻卡 ----------
def fold(s):
    """İrsoy → irsoy：去掉重音、轉小寫，讓作者姓氏比對不受拼法影響。"""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()

def cards():
    """notes/ 裡由 analyze-literature 產出的文獻卡（有 source_pdf 的才算）。回傳 {檔名主幹: 資訊}"""
    out = {}
    if not NOTES.exists(): return out
    for p in sorted(NOTES.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.name == "README.md" or "source_pdf:" not in text[:400]: continue
        toks = p.stem.split("_")
        year = next((t for t in toks if re.fullmatch(r"(19|20)\d\d", t)), "")
        out[p.stem] = {"path": str(p), "text": text, "surname": fold(toks[0]), "year": year,
                       "pages": card_pages(text), "apa": apa_line(text)}
        out[p.stem]["cite"] = cite_name(out[p.stem]["apa"], toks[0], year)
    return out

def pool(st):
    """初篩之後只剩暫存清單裡的卡；之前是 notes/ 全部"""
    cs = cards()
    if not at_least(st, "planning"): return cs
    keep = set(st.get("shortlist", []))
    return {k: v for k, v in cs.items() if k in keep}

HEADS = ("研究核心目的", "研究方法", "實證結果")

def excerpt(text, limit=600):
    """初篩用的摘錄：APA＋研究目的、方法、結果各前幾百字，不必讀整張卡"""
    body = text.split("附錄：引用的原文片段")[0]
    lines = body.splitlines(); out = [f"APA：{apa_line(text) or '（文獻卡沒有 APA）'}"]
    for h in HEADS:
        at = next((i for i, l in enumerate(lines) if h in l and len(l.strip()) < 40), None)
        if at is None: continue
        seg = []
        for l in lines[at + 1:]:
            if any(k in l for k in HEADS + ("結論", "文獻引用")) and len(l.strip()) < 40: break
            if l.strip() and l.strip() != "---": seg.append(l.strip())
        txt = re.sub(r"\s*\[[\d,\s\-–]+\]", "", " ".join(seg))
        out.append(f"【{h}】{txt[:limit]}{'…' if len(txt) > limit else ''}")
    if len(out) == 1:
        out.append(re.sub(r"\s+", " ", body.split("---", 2)[-1])[:limit * 2])
    return "\n".join(out)

def expand(spec):
    pages = set()
    for a, b in re.findall(r"(\d+)\s*(?:[–\-~～至到]\s*(\d+))?", spec):
        a = int(a); b = int(b) if b else a
        if 0 < a <= b <= a + 60: pages.update(range(a, b + 1))
    return pages

def card_pages(text):
    """文獻卡裡標過的頁碼：第 1, 3–4 頁／p. 5／pp. 2-3／Page 7"""
    pages = set()
    for spec in re.findall(r"第\s*([\d\s,，、–\-~～至到]+?)\s*頁", text): pages |= expand(spec)
    for spec in re.findall(r"\b(?:pp?\.|[Pp]age)\s*([\d\s,–\-]+)", text): pages |= expand(spec)
    return pages

def cite_name(apa, first, year):
    """從 APA 的作者欄決定內文怎麼寫：1 位 Horvath、2 位 Ruf & Wang、3 位以上 Horvath et al."""
    authors = re.split(r"\(\s*(?:19|20)\d\d", apa)[0]
    names = re.findall(r"([A-ZÀ-ÖØ-Ýİ][\w'’\-]+),\s*(?:[A-Z]\.\s*-?)+", authors)
    if len(names) == 2: return f"{names[0]} & {names[1]}, {year}"
    if len(names) >= 3: return f"{names[0]} et al., {year}"
    return f"{names[0] if names else first}, {year}"

def apa_line(text):
    m = re.search(r"APA[^\n]*?[：:]\s*(.*)", text)
    if not m: return ""
    line = m.group(1).strip().lstrip("*").strip()
    if len(line) < 15:   # APA 寫在下一行
        rest = text[m.end():].lstrip("\n")
        line = rest.split("\n", 1)[0].strip()
    line = re.sub(r"\s*\[[^\]]*\]\s*$", "", line)                          # 去掉 NotebookLM 的 [1, 2]、[第 1 頁，標題頁]
    line = re.sub(r"\s*[（(](出自|出處|Section|Title)[^）)]*[）)]\s*$", "", line)
    return line.replace("**", "").strip()

# ---------- 引用 ----------
CITE = re.compile(r"[（(]([^（）()]*?(?:19|20)\d\d[^（）()]*?)[）)]")
ONE = re.compile(r"^\s*(?P<who>[^,，;；]+?)\s*[,，]\s*(?P<year>(?:19|20)\d\d)[a-z]?\s*[,，]\s*"
                 r"(?:第\s*(?P<p1>[\d\s,，、–\-~～至到]+?)\s*頁|pp?\.\s*(?P<p2>[\d\s,–\-]+)|(?P<sec>[^,，;；（）()]{2,40}?)\s*節)\s*$")

def parse_cites(sentence):
    """回傳 [(作者字串, 年, {頁碼}, 原文)]；格式不對的以 None 標記頁碼"""
    found = []
    for m in CITE.finditer(sentence):
        prev = None
        for part in re.split(r"[;；]", m.group(1)):
            if not re.search(r"(19|20)\d\d", part):
                pg = re.fullmatch(r"\s*(?:第\s*([\d\s,，、–\-~～至到]+?)\s*頁|pp?\.\s*([\d\s,–\-]+))\s*", part)
                if pg and prev: found.append((prev[0], prev[1], expand(pg.group(1) or pg.group(2)), part.strip()))
                elif part.strip(): found.append((None, None, None, part.strip()))
                continue
            g = ONE.match(part)
            if g: prev = (g.group("who"), g.group("year"))
            loc = g and (g.group("sec").strip() if g.group("sec") else expand(g.group("p1") or g.group("p2")))   # 沒有頁碼的論文用章節
            found.append((g.group("who"), g.group("year"), loc, part.strip()) if g
                         else (None, None, None, part.strip()))
    return found

def match_card(who, year, cs):
    first = fold(re.split(r"\s+(?:et al\.?|&|and|與|等)\s*|\s*[&、]\s*", who.strip())[0]).split()[-1] if who.strip() else ""
    for stem, c in cs.items():
        if c["year"] == year and (c["surname"] == first or c["surname"].startswith(first) or first.startswith(c["surname"])):
            return stem
    return None

SEVERAL = re.compile(r"(兩|二|三|這兩|這三)(篇|者|項研究|份文獻)")

NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|％|倍|萬|億)?")

def numbers(sentence):
    """句子裡要核對的數字（不含引用括號裡的年份頁碼）：兩位數以上，或帶 % 倍 的"""
    body = CITE.sub("", sentence)
    out = []
    for n, unit in NUM.findall(body):
        plain = n.replace(",", "")
        if unit or len(plain.split(".")[0]) >= 2 or "." in plain: out.append(plain + (unit or "").replace("％", "%"))
    return out

def num_in(num, text):
    t = re.sub(r"(?<=\d),(?=\d{3})", "", text).replace("％", "%")
    core = re.match(r"[\d.]+", num).group(0); unit = num[len(core):]
    pat = r"(?<![\d.])" + re.escape(core) + (r"\s*" + re.escape(unit) if unit else r"(?![\d])")
    return re.search(pat, t) is not None

# ---------- plan.md ----------
def parse_plan():
    txt = PLAN.read_text(encoding="utf-8", errors="replace")
    rows = []
    for line in txt.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.strip().startswith("|") and len(cells) >= 4 and cells[0].isdigit():
            rows.append({"n": int(cells[0]), "topic": cells[1], "cards": [c.strip().removesuffix(".md").split("/")[-1]
                         for c in re.split(r"[,，、;；\s]+", cells[2]) if c.strip()], "question": cells[3]})
    q = re.search(r"研究問題[^\n：:]*[：:]\s*(.+)", txt)
    return txt, (q.group(1).strip() if q else ""), rows

def dropped(txt):
    """「- 暫存但不採用：A（理由）、B（理由）」→ {A: 理由}"""
    m = re.search(r"暫存但不採用[^\n：:]*[：:]\s*(.+)", txt)
    if not m: return None
    return {k.strip().removesuffix(".md"): why.strip() for k, why in re.findall(r"([\w.\-]+)\s*[（(]([^）)]*)[）)]", m.group(1))}

def check_plan(st):
    if not PLAN.exists(): return ["找不到 plan.md"], None
    txt, q, rows = parse_plan(); cs = pool(st); bad = []
    if not q: bad.append("開頭少了「研究問題」那一行（格式：- 研究問題：內容）")
    if len(rows) < 3: bad.append("分節表至少要 3 列：2 個以上的主題節，加最後一列「研究缺口」（每列：| 節 | 主題 | 文獻卡 | 這一節要回答的問題 |）")
    elif GAP not in rows[-1]["topic"]: bad.append(f"最後一節的主題要是「研究{GAP}」")
    used = set()
    for r in rows:
        tag = f"第 {r['n']} 節"
        if (sc := simplified_in(r["topic"] + r["question"])): bad.append(f"{tag}有簡體字：{'、'.join(sc)}")
        unknown = [c for c in r["cards"] if c not in cs]
        if unknown: bad.append(f"{tag}的文獻卡 {'、'.join(unknown)} 不在初篩的暫存清單裡。只能用：{'、'.join(cs)}")
        used |= {c for c in r["cards"] if c in cs}
        if GAP not in r["topic"] and len(cs) >= 2 and len(set(r["cards"])) < 2:
            bad.append(f"{tag}只用了一張文獻卡。文獻回顧是把不同文獻放在一起比較，每個主題節至少放 2 張卡")
    if (q and (sc := simplified_in(q))): bad.append(f"研究問題有簡體字：{'、'.join(sc)}")
    drop = dropped(txt)
    if drop is None: bad.append("少了「- 暫存但不採用：」那一行。暫存清單裡沒放進任何一節的卡，要寫在這裡並附理由；全部都用到就寫「- 暫存但不採用：無」")
    else:
        if (both := [c for c in drop if c in used]): bad.append(f"{'、'.join(both)} 已經放進分節表，就不要再寫在「暫存但不採用」")
        if (nowhy := [c for c, why in drop.items() if len(why) < 6]): bad.append(f"「暫存但不採用」的 {'、'.join(nowhy)} 理由太短，要說明為什麼最後沒用上")
        if (lost := [c for c in cs if c not in used and c not in drop]):
            bad.append(f"暫存清單裡的 {'、'.join(lost)} 沒有放進任何一節，也沒有寫在「暫存但不採用」。每一張都要有去處")
    return bad, rows

# ---------- review.md ----------
def sections(txt):
    """[(標題, 內文)]，不含參考文獻"""
    parts = re.split(r"^##\s+(.+)$", txt, flags=re.M)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2) if "參考文獻" not in parts[i]]

def sentences(body):
    text = "\n".join(l for l in body.splitlines() if l.strip() and not l.lstrip().startswith(("#", "|", ">", "<!--")))
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M)
    return [s.strip() for s in re.split(r"(?<=[。！？])", text.replace("\n", "")) if len(s.strip()) > 4]

def check_review(rows, st):
    if not REVIEW.exists(): return ["找不到 review.md"], {}
    txt = REVIEW.read_text(encoding="utf-8", errors="replace"); cs = pool(st); bad = []; usage = {}
    secs = sections(txt)
    if len(secs) != len(rows):
        bad.append(f"review.md 有 {len(secs)} 個 ## 節，plan.md 有 {len(rows)} 節。要一節對一節，順序相同")
    for (title, body), r in zip(secs, rows):
        if r["topic"] not in title: bad.append(f"第 {r['n']} 節的標題要包含 plan.md 的主題「{r['topic']}」（現在是「{title}」）")
    for si, (title, body) in enumerate(secs, 1):
        cited_here, compared = set(), False
        ss = sentences(body)
        if not ss: bad.append(f"第 {si} 節是空的")
        for s in ss:
            short = s[:40] + ("…" if len(s) > 40 else "")
            cites = parse_cites(s)
            if not cites:
                bad.append(f"第 {si} 節這句沒有出處：「{short}」。每一句都要在句尾標（作者, 年，第 N 頁）"); continue
            stems = []
            for who, year, pages, raw in cites:
                if who is None:
                    bad.append(f"第 {si} 節引用格式不對：（{raw}）。要寫成（Horvath et al., 2019，第 10 頁），一定要有頁碼"); continue
                stem = match_card(who, year, cs)
                if not stem:
                    bad.append(f"第 {si} 節引用的（{raw}）不在暫存清單的文獻卡裡。只能引用：" +
                               "、".join(f"（{c['cite']}，第 N 頁）" for c in cs.values())); continue
                stems.append(stem); cited_here.add(stem)
                if isinstance(pages, str):
                    if cs[stem]["pages"]:
                        bad.append(f"第 {si} 節（{raw}）：這張文獻卡有標頁碼，要寫第 N 頁，不要寫章節")
                    elif fold(pages) not in fold(cs[stem]["text"]):
                        bad.append(f"第 {si} 節（{raw}）：文獻卡 {stem} 裡找不到「{pages}」這個章節名稱，要照卡上寫的抄")
                    continue
                miss = sorted(p for p in pages if p not in cs[stem]["pages"])
                if miss: bad.append(f"第 {si} 節（{raw}）的第 {'、'.join(map(str, miss))} 頁，在文獻卡 {stem} 裡沒有出現過。頁碼要照文獻卡上標的抄")
            if len(cs) >= 2 and SEVERAL.search(CITE.sub("", s)) and len(set(stems)) < 2:
                bad.append(f"第 {si} 節這句說的是多篇文獻，卻只引用了 {len(set(stems))} 篇：「{short}」。要把它說的每一篇都標出來，或改成只講那一篇")
            for n in numbers(s):
                if stems and not any(num_in(n, cs[st]["text"]) for st in stems):
                    bad.append(f"第 {si} 節的數字「{n}」在它引用的文獻卡裡找不到：「{short}」。數字要和文獻卡一模一樣，不可以自己估算或換算")
            if len(set(stems)) >= 2: compared = True
        usage[title] = cited_here
        if GAP in title: continue
        if len(cs) >= 2 and len(cited_here) < 2:
            bad.append(f"第 {si} 節「{title}」只引用了 {len(cited_here)} 篇。主題節要把至少 2 篇放在一起比較（誰發現什麼、哪裡一致、哪裡不同）")
        elif len(cs) >= 2 and not compared:
            bad.append(f"第 {si} 節「{title}」每一句都只講一篇，像是摘要排在一起。至少要有一句同時引用 2 篇、"
                       "直接比較它們（例如：A 發現……，B 卻發現……（A, 年，第 N 頁；B, 年，第 N 頁））")
        if re.search(r"^\s*([-*•]|\d+[.、])\s+", body, flags=re.M):
            bad.append(f"第 {si} 節「{title}」用了條列。主題節要寫成一段文字，句子之間要有連接（但是、同樣地、相較之下）")
        if si <= len(rows) and (skipped := [c for c in rows[si - 1]["cards"] if c in cs and c not in cited_here]):
            bad.append(f"第 {si} 節「{title}」沒有引用 plan.md 排給它的 {'、'.join(skipped)}。排進這一節的卡都要用到；真的用不到，就回去改 plan.md")
    if (sc := simplified_in(txt)): bad.append(f"有簡體字：{'、'.join(sc)}。一律用台灣繁體中文")
    return bad, usage

def write_refs(usage):
    cs = cards(); used = sorted({s for v in usage.values() for s in v}, key=lambda s: (cs[s]["surname"], cs[s]["year"]))
    txt = REVIEW.read_text(encoding="utf-8")
    txt = re.split(r"^##\s+參考文獻.*$", txt, flags=re.M)[0].rstrip()
    refs = [cs[s]["apa"] or f"（{s} 的文獻卡沒有 APA 引用，請手動補上）" for s in used]
    REVIEW.write_text(txt + "\n\n## 參考文獻\n\n" + "\n\n".join(refs) + "\n\n<!-- 參考文獻由程式從文獻卡的 APA 欄位產生，不是模型寫的 -->\n", encoding="utf-8")
    return used

# ---------- 給模型的指示 ----------
def card_list(st):
    return "\n".join(f"   - {ME} show {k}　（內文引用寫成：（{c['cite']}，{'第 N 頁' if c['pages'] else '某某 節'}））"
                     for k, c in pool(st).items())

ASK_HOWTO = """1. 使用者還沒講研究問題，就先問他：這篇文獻回顧要回答什麼問題？給誰看？然後【這一輪到此結束】，等他回覆。
   （他已經講過就不用問，直接到第 2 步。）
2. 執行：{me} question "研究問題"
   接著照它印的指示執行 screen，程式會一篇一篇問模型，判斷每篇和研究問題有沒有關係。"""

PLAN_HOWTO = """1. 逐一執行下面的指令，把暫存清單裡每張文獻卡的本文【從頭讀到尾】（不要用讀檔工具開整個檔案，附錄很長、會把你的記憶塞爆）：
{cards}
2. 這是第二輪篩選：讀完全文，決定哪些真的放進文獻回顧、怎麼分組。
3. 寫 plan.md，格式如下（照抄格式，內容換成你的）：

- 研究問題：{question}
- 讀者：修過投資學的金融系大三學生
- 暫存但不採用：卡片檔名（為什麼最後沒用上）、卡片檔名（理由）　← 全部都用到就寫「無」

| 節 | 主題 | 文獻卡 | 這一節要回答的問題 |
|---|---|---|---|
| 1 | 計算速度與校準瓶頸 | Horvath_2019_deep_learning_volatility, Ruf_Wang_2020_NN_option_pricing_review | 各文獻怎麼解決傳統方法太慢的問題？ |
| 2 | 定價準確度的證據 | Horvath_2019_deep_learning_volatility, Ruf_Wang_2020_NN_option_pricing_review | 準確度怎麼衡量？結果一致嗎？ |
| 3 | 研究{gap} | Horvath_2019_deep_learning_volatility, Ruf_Wang_2020_NN_option_pricing_review | 各文獻自己承認的限制有哪些？還有什麼沒人做？ |

規則：
- 按【主題】分節，不是一篇一節。每個主題節至少放 2 張文獻卡，因為文獻回顧是比較，不是摘要。
- 最後一節固定是「研究{gap}」。
- 文獻卡欄寫 notes/ 裡的檔名（不含 .md），只能用上面列的卡。
- 上面列的每一張卡都要有去處：放進某一節，或寫在「暫存但不採用」並附理由。
4. 執行：{me} check-plan
5. 通過後把 plan.md 貼給使用者，問他這樣分可以嗎？然後【這一輪到此結束】，等他回覆。"""

WRITE_HOWTO = """照 plan.md 寫 review.md。格式：

# 文獻回顧：（題目）

- 研究問題：（和 plan.md 一樣）

## 1. 計算速度與校準瓶頸

（一段 3–6 句。每一句句尾都要標出處，例如：）
傳統的粗糙波動率模型沒有封閉解，必須依賴蒙地卡羅模擬，校準時面臨計算瓶頸（Horvath et al., 2019，第 3 頁）。
Ruf 與 Wang 回顧了超過 150 篇以神經網路做選擇權定價的文獻（Ruf & Wang, 2020，第 1 頁）。
兩篇都指出……，但……（Horvath et al., 2019，第 7 頁；Ruf & Wang, 2020，第 5 頁）。

規則（程式會逐句檢查，不過就要改）：
- 【每一句】句尾都要有（作者, 年，第 N 頁）。同一句用到兩篇就用「；」隔開放在同一個括號裡。
- 頁碼只能抄文獻卡上標的頁碼。文獻卡沒有頁碼、只標章節的（例如「Media Coverage 節」），就寫（作者, 年，Media Coverage 節）。文獻卡寫「文中未述」的，就不可以寫成有。
- 數字要和文獻卡一模一樣，不可以自己估、四捨五入或換算。
- 每個主題節至少引用 2 篇，寫出它們【一致在哪、不同在哪】，不要一篇一段各講各的。
- 「研究{gap}」那一節寫各文獻自己承認的限制，以及把幾篇放在一起看才看得出來、還沒人做的事。
- 節標題要包含 plan.md 的主題，順序相同。
- 不要自己寫參考文獻，也不要寫「參考文獻由程式產生」之類的說明，程式會自己附上。
- 台灣繁體中文。
寫完執行：{me} check"""

def say_start(st):
    print("【第 1 關】確定研究問題\n")
    print(ASK_HOWTO.format(me=ME))
    if st.get("auto"):
        print("\n（使用者已經把決定交給你：根據他的要求自己寫一句研究問題，直接執行 question，不用問。）")

def say_screening(st):
    left = [s for s in cards() if s not in st.get("judged", {})]
    print(f"【第 2 關：逐篇初篩】研究問題：{st['question']}")
    print(f"還有 {len(left)} / {len(cards())} 篇沒判斷。初篩由程式一篇一篇問模型，【你不用自己判斷，也不要自己讀文獻卡】。")
    print(f"執行：{ME} screen")
    print("它一次最多跑約 90 秒；印出「還有 N 篇」就再執行一次，直到印出「初篩完成」。中間【不要停下來問使用者】。")

def write_screening(st):
    cs = cards(); done = st.get("judged", {})
    rows = [f"| {i} | {s} | {done[s]['verdict']} | {done[s]['reason'].replace('|', '／')} |" for i, s in enumerate(cs, 1) if s in done]
    keep = [s for s in cs if done.get(s, {}).get("verdict") == YES]
    SCREEN.write_text(f"# 初篩紀錄\n\n- 研究問題：{st.get('question', '')}\n- 已判斷 {len(rows)} / {len(cs)} 篇，"
                      f"暫存（相關）{len(keep)} 篇\n\n| # | 文獻卡 | 判斷 | 理由 |\n|---|---|---|---|\n" + "\n".join(rows) +
                      "\n\n<!-- 這份紀錄由程式產生；要撈回或剔除請用 review.py include／exclude -->\n", encoding="utf-8")
    return keep

def say_screened(st):
    keep = write_screening(st)
    print(f"【初篩完成的停頓點】{len(cards())} 篇都判斷過了，暫存（相關）{len(keep)} 篇：{'、'.join(keep) or '（沒有）'}")
    print("完整紀錄在 screening.md。")
    if st.get("auto"):
        print(f"使用者交給你決定，直接執行：{ME} approve"); return
    print("- 使用者還沒看過 → 把 screening.md 的「相關」和「不相關」各列一份給他（檔名＋理由），問他要不要撈回或剔除哪幾篇，然後【這一輪到此結束】。")
    print(f'- 使用者要撈回某篇 → {ME} include 檔名 "使用者說的理由"；要剔除 → {ME} exclude 檔名 "理由"')
    print(f"- 使用者說可以 → {ME} approve")

def say_plan(st):
    if st.get("note"): print("⚠ " + st["note"] + "\n")
    print("【第 3 關】第二輪：讀暫存清單的全文 → 寫分節架構 plan.md\n")
    print(PLAN_HOWTO.format(cards=card_list(st), gap=GAP, me=ME, question=st.get("question", "")))
    if st.get("auto"):
        print("\n（使用者已經把決定交給你：分節由你決定，check-plan 通過後直接執行 approve，不用停下來問。）")

# ---------- 指令 ----------
def cmd_next(st):
    if not cards():
        sys.exit("notes/ 裡沒有文獻卡（要有 source_pdf 的 .md）。停下來告訴使用者：請先把 PDF 放進 papers/，用 analyze-literature 做出文獻卡，再叫你繼續。")
    stage = st["stage"]
    if stage == "start": say_start(st)
    elif stage == "screening":
        if any(s not in st.get("judged", {}) for s in cards()): say_screening(st)
        else: finish_screening(st)
    elif stage == "screened": say_screened(st)
    elif stage == "planning": say_plan(st)
    elif stage == "planned":
        print("【第 3 關的停頓點】plan.md 已經通過檢查。")
        print("- 使用者還沒看過 → 把 plan.md 貼給他，問這樣分可以嗎，然後這一輪結束。")
        print(f"- 使用者說可以 → 執行：{ME} approve")
        print(f"- 使用者要改 → 改 plan.md，再執行：{ME} check-plan")
    elif stage == "approved":
        print("【第 4 關】寫 review.md\n"); print(WRITE_HOWTO.format(gap=GAP, me=ME))
    else:
        print("文獻回顧已經完成：review.md（含程式產生的參考文獻）；初篩紀錄在 screening.md。")
        print("把 review.md 的位置告訴使用者，並提醒他：程式只能檢查出處、頁碼、數字有沒有對上，")
        print("【一句話的意思有沒有被寫歪】要他自己對照文獻卡讀一遍。")

def cmd_question(st, args):
    q = " ".join(args).strip()
    if at_least(st, "screening") and st.get("judged"):
        sys.exit("已經開始初篩了，研究問題不能中途換。真的要換，請使用者刪掉 .review-state.json 重新開始。")
    if len(q) < 8: sys.exit(f'研究問題太短。要寫成一句完整的問題，例如：{ME} question "新聞報導如何影響房價與房市交易？"')
    if (sc := simplified_in(q)): sys.exit(f"研究問題有簡體字：{'、'.join(sc)}")
    st = {**st, "question": q, "stage": "screening", "judged": {}}; save(st)
    print(f"已記錄研究問題：{q}\n共有 {len(cards())} 張文獻卡。\n")
    say_screening(st)

BUDGET = 90   # 秒；OpenCode 的指令有時間上限，分批跑

def judge_one(key, st, stem, c, model):
    """問模型一篇；理由不合格就把問題告訴它重問一次。回傳 {"verdict","reason"}"""
    fb = ""
    for _ in range(2):
        verdict, reason = screen.ask(key, st["question"], excerpt(c["text"]), fb, model=model)
        probs = []
        if len(reason) < 10: probs.append("理由太短，要說出這篇研究什麼、和研究問題哪裡對得上或對不上")
        if verdict == YES and c["pages"]:   # 文獻卡沒有頁碼（只標章節）的就不要求
            pages = card_pages(reason)
            if not pages: probs.append("判相關要在理由附摘錄裡出現過的頁碼（第 N 頁）")
            elif (miss := sorted(p for p in pages if p not in c["pages"])): probs.append(f"第 {'、'.join(map(str, miss))} 頁不在文獻卡裡")
        if (sc := simplified_in(reason)): probs.append(f"有簡體字：{'、'.join(sc)}，要用台灣繁體中文")
        if not probs: return {"verdict": verdict, "reason": reason}
        fb = "；".join(probs)
    return {"verdict": verdict, "reason": reason + f"（程式提醒：{fb}）"}

def cmd_screen(st, args):
    if st["stage"] != "screening": sys.exit(f"現在不是初篩階段。執行：{ME} next")
    key = screen.api_key()
    if not key:
        sys.exit("找不到 Ollama 的 API key。停下來請使用者做以下其中一件事，做完再叫你繼續：\n"
                 "  1. 在工作資料夾建一個檔案 .ollama_key，內容只有他的 Ollama API key 一行；或\n"
                 "  2. 把 key 設成環境變數 OLLAMA_API_KEY 後重開 OpenCode。\n"
                 "（就是他在 OpenCode 設定 Ollama Cloud 時貼的那一把 key。不要叫他把 key 貼在對話裡。）")
    model = args[args.index("--model") + 1] if "--model" in args else screen.MODEL
    cs = cards(); t0 = time.time()
    for stem, c in cs.items():
        if stem in st.get("judged", {}): continue
        if time.time() - t0 > BUDGET: break
        try: j = judge_one(key, st, stem, c, model)
        except RuntimeError as e:
            write_screening(st)
            sys.exit(f"初篩中斷（已判斷的都存好了，再執行一次 screen 會接著做）：{e}")
        st = {**st, "judged": {**st.get("judged", {}), stem: j}}; save(st)
        print(f"[{len(st['judged'])}/{len(cs)}] {stem} → {j['verdict']}", flush=True)
    write_screening(st)
    left = len(cs) - len(st.get("judged", {}))
    if left:
        print(f"\n還有 {left} 篇。【不要停下來】馬上再執行一次：{ME} screen"); return
    print("\n初篩完成。"); finish_screening(st)

def finish_screening(st):
    st = {**st, "stage": "screened"}; save(st); say_screened(st)

def cmd_override(st, args, verdict):
    if st["stage"] != "screened": sys.exit(f"初篩全部做完之後，才能撈回或剔除。執行：{ME} next")
    if len(args) < 2: sys.exit(f'格式：{ME} {"include" if verdict == YES else "exclude"} 檔名 "理由"')
    stem = args[0].removesuffix(".md").split("/")[-1]
    if stem not in cards(): sys.exit(f"notes/ 裡沒有 {stem}")
    why = "（使用者決定）" + " ".join(args[1:]).strip()
    st = {**st, "judged": {**st["judged"], stem: {"verdict": verdict, "reason": why}}}; save(st)
    print(f"已改成：{stem} → {verdict}\n"); say_screened(st)

def cmd_show(st, args):
    if not args: sys.exit(f"格式：{ME} show 檔名")
    stem = args[0].removesuffix(".md").split("/")[-1]; cs = pool(st)
    if stem not in cs: sys.exit(f"{stem} 不在暫存清單裡。可以看的：{'、'.join(cs)}")
    body = cs[stem]["text"].split("## 附錄：引用的原文片段")[0].rstrip().rstrip("-").rstrip()
    print(body); print(f"\n（以上是 {stem} 的本文；附錄的原文片段省略。內文引用寫成：（{cs[stem]['cite']}，{'第 N 頁' if cs[stem]['pages'] else '某某 節'}））")

def cmd_check_plan(st):
    if not at_least(st, "planning"): sys.exit(f"還不能寫架構：初篩還沒做完或還沒給使用者確認。執行：{ME} next")
    bad, rows = check_plan(st)
    if bad:
        print(f"PLAN 未通過，有 {len(bad)} 個問題："); [print("  - " + b) for b in bad]
        print(f"\n修改 plan.md 後再執行：{ME} check-plan"); return
    st = {**st, "stage": "planned", "plan_hash": digest(PLAN)}; st.pop("note", None); save(st)
    print(f"PLAN OK：{len(rows)} 節。")
    if st.get("auto"): print(f"使用者交給你決定，直接執行：{ME} approve")
    else: print("把 plan.md 貼給使用者，問他這樣分可以嗎，然後【這一輪到此結束】，等他回覆。")

def cmd_approve(st):
    if st["stage"] == "screened":
        keep = [s for s, j in st["judged"].items() if j["verdict"] == YES]
        if len(keep) < 2:
            sys.exit(f"暫存（相關）只有 {len(keep)} 篇，寫不成文獻回顧（至少要 2 篇才能比較）。停下來告訴使用者："
                     "可以用 include 撈回幾篇、放寬研究問題，或回到 fetch-literature 補文獻。")
        st = {**st, "stage": "planning", "shortlist": keep}; save(st)
        print(f"已記錄：使用者同意初篩結果，暫存清單 {len(keep)} 篇。【不要停下來】接著做第二輪。\n"); say_plan(st); return
    if st["stage"] in ("start", "screening", "planning"):
        sys.exit(f"現在沒有東西要確認。執行：{ME} next")
    st = {**st, "stage": "approved"}; save(st)
    print("已記錄：使用者同意分節架構。【不要停下來】這一輪就接著寫 review.md。\n")
    print(WRITE_HOWTO.format(gap=GAP, me=ME))

def cmd_check(st):
    if not at_least(st, "approved"): sys.exit(f"還不能寫：分節架構還沒經過使用者確認。執行：{ME} next")
    _, _, rows = parse_plan()
    bad, usage = check_review(rows, st)
    if bad:
        print(f"REVIEW 未通過，有 {len(bad)} 個問題：")
        for b in bad[:15]: print("  - " + b)
        if len(bad) > 15: print(f"  …還有 {len(bad) - 15} 個，先改上面的")
        print(f"\n修改 review.md 後再執行：{ME} check"); return
    used = write_refs(usage)
    st = {**st, "stage": "done"}; save(st)
    n = sum(len(sentences(b)) for _, b in sections(REVIEW.read_text(encoding="utf-8")))
    print(f"REVIEW OK：{len(rows)} 節、{n} 句，每一句都有出處，頁碼與數字都在文獻卡裡找得到。")
    print(f"已從文獻卡產生參考文獻 {len(used)} 筆，附在 review.md 最後。")
    print("回報使用者：review.md 的位置、各節引用了哪幾篇、初篩排除了幾篇（screening.md）；並提醒他程式查不出「意思寫歪」，要自己對照文獻卡讀一遍。")

def cmd_auto(st, args):
    said = " ".join(args).strip()
    if not any(w in said for w in AUTO_WORDS):
        sys.exit("auto 只能在使用者明說「全部交給你、不用問我」時使用，而且要附上他的原話，例如：\n"
                 f'  {ME} auto "全部交給你，不用問我"')
    st = {**st, "auto": True}; save(st)
    print("已記錄：使用者把決定交給你。最後回報時要說明哪些是你替他決定的。\n")
    cmd_next(st)

def main():
    args = sys.argv[1:]
    if not args: print(__doc__); return
    st = load(); cmd = args[0]
    table = {"next": lambda: cmd_next(st), "question": lambda: cmd_question(st, args[1:]),
             "screen": lambda: cmd_screen(st, args[1:]), "include": lambda: cmd_override(st, args[1:], YES),
             "exclude": lambda: cmd_override(st, args[1:], NO), "check-plan": lambda: cmd_check_plan(st), "show": lambda: cmd_show(st, args[1:]),
             "approve": lambda: cmd_approve(st), "check": lambda: cmd_check(st), "auto": lambda: cmd_auto(st, args[1:])}
    if cmd not in table: print(__doc__); sys.exit(1)
    table[cmd]()

if __name__ == "__main__":
    main()
