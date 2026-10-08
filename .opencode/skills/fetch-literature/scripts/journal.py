#!/usr/bin/env python3
"""期刊 ISSN 對照表的查詢與新增：AI 去查、人來選、程式來寫。

  python journal.py lookup "刊名"            到 OpenAlex 查候選期刊（同名的會一起列出來）
  python journal.py add ISSN "等級"          用 ISSN 再查一次確認，寫進 references/journals.md
                                              等級寫清楚來源，例如「國科會 A+」「ABDC A」；不知道就寫「未查」
金鑰：有環境變數 OPENALEX_API_KEY 就帶上（沒帶也能查，但和同網路的人共用很小的額度）。
"""
import datetime, json, os, pathlib, re, sys, urllib.parse, urllib.request

for _s in (sys.stdout, sys.stderr):   # Windows 的主控台是 cp950，不改成 UTF-8 會當掉或變亂碼
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

ME = "python .opencode/skills/fetch-literature/scripts/journal.py"
TABLE = pathlib.Path(__file__).resolve().parent.parent / "references" / "journals.md"
API = "https://api.openalex.org/sources"
FIELDS = "display_name,issn_l,issn,host_organization_name,works_count,is_core"
ISSN = re.compile(r"^\d{4}-\d{3}[\dXx]$")

def get(url):
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if key: url += ("&" if "?" in url else "?") + "api_key=" + urllib.parse.quote(key)
    req = urllib.request.Request(url, headers={"User-Agent": "nkust-academic-ai-agent"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        sys.exit(f"OpenAlex 回應錯誤 {e.code}，稍後再試；若是 429 代表額度用完，請設定 OPENALEX_API_KEY")
    except urllib.error.URLError as e:
        sys.exit(f"連不上 OpenAlex：{e}")

def norm(name):
    """比對刊名用：小寫、& 換成 and、去掉開頭的 the 與標點"""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"^the ", "", re.sub(r"\s+", " ", s).strip())

def rows():
    if not TABLE.exists(): return []
    return [l for l in TABLE.read_text(encoding="utf-8").splitlines() if l.startswith("| ") and ISSN.match(l.split("|")[2].strip() or "x")]

def cmd_lookup(args):
    name = " ".join(args).strip()
    if not name: sys.exit(f'格式：{ME} lookup "刊名"')
    have = {r.split("|")[2].strip() for r in rows()}
    data = get(f"{API}?search={urllib.parse.quote(name)}&select={FIELDS}&per-page=6") or {"results": []}
    res = [r for r in data["results"] if r.get("issn_l")]
    if not res:
        print(f"OpenAlex 查不到「{name}」。請使用者確認刊名拼法，或直接提供 ISSN。"); return
    exact = [r for r in res if norm(r["display_name"]) == norm(name)]
    print(f"「{name}」的候選期刊（收錄篇數越多、出版社越知名，通常就是要找的那本）：\n")
    for i, r in enumerate(res, 1):
        tags = []
        if r in exact: tags.append("刊名完全相符")
        if not r.get("is_core"): tags.append("非核心期刊，小心")
        if r["issn_l"] in have: tags.append("已在對照表")
        print(f"  {i}. {r['display_name']}｜ISSN {r['issn_l']}｜{r.get('host_organization_name') or '出版社不明'}｜"
              f"收錄 {r.get('works_count', 0):,} 篇" + (f"｜{'、'.join(tags)}" if tags else ""))
    if len(exact) == 1 and exact[0]["issn_l"] in have:
        print(f"\n這本已經在對照表裡（ISSN {exact[0]['issn_l']}），不用新增，直接拿這個 ISSN 去查文獻。")
    elif len(exact) == 1 and exact[0].get("is_core"):
        print(f"\n只有一本刊名完全相符，且是核心期刊：可以直接執行 {ME} add {exact[0]['issn_l']} \"等級\"")
    else:
        print("\n沒有唯一完全相符的那一本：把上面的清單貼給使用者，請他選是哪一本，再執行 add。不可以自己猜。")

def cmd_add(args):
    if len(args) < 2: sys.exit(f'格式：{ME} add ISSN "等級"（等級寫來源，例如「國科會 A+」；不知道就寫「未查」）')
    issn, grade = args[0].upper(), " ".join(args[1:]).strip()
    if not ISSN.match(issn): sys.exit(f"ISSN 格式不對：{issn}（應為 1234-567X）")
    if grade != "未查" and not re.search(r"[A-Za-z]", grade):
        sys.exit("等級要寫清楚來源與級別，例如「國科會 A+」「ABDC A」；沒有可靠來源就寫「未查」，不可以自己猜")
    for r in rows():
        cells = [c.strip() for c in r.split("|")]
        if cells[2] == issn: sys.exit(f"已經在對照表裡了：{cells[1]}（{issn}）")
    s = get(f"{API}/issn:{issn}?select={FIELDS}")
    if not s: sys.exit(f"OpenAlex 查不到 ISSN {issn}，請再確認")
    row = (f"| {s['display_name']} | {s['issn_l']} | {grade} | {s.get('host_organization_name') or '不明'} | "
           f"{datetime.date.today()} |")
    text = TABLE.read_text(encoding="utf-8").rstrip("\n")
    TABLE.write_text(text + "\n" + row + "\n", encoding="utf-8")
    print(f"已加入對照表：{s['display_name']}｜{s['issn_l']}｜{grade}｜{s.get('host_organization_name')}")
    print("告訴使用者加了哪一本，並請他打開 references/journals.md 看一眼。")

def main():
    a = sys.argv[1:]
    table = {"lookup": cmd_lookup, "add": cmd_add}
    if not a or a[0] not in table: print(__doc__); sys.exit(1)
    table[a[0]](a[1:])

if __name__ == "__main__":
    main()
