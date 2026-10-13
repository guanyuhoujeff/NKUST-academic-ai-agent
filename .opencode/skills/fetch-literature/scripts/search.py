#!/usr/bin/env python3
"""向 OpenAlex 查文獻、寫出 literature.md：期刊範圍由程式讀對照表決定，AI 不用自己組網址、不用自己挑期刊。

  python search.py "關鍵字"                         查對照表裡全部期刊（＝頂刊）
  python search.py "關鍵字" --journal "刊名或ISSN"   只查這一本（必須已在對照表裡）
  python search.py "關鍵字" --from 2015             只要 2015 年以後的
  python search.py "關鍵字" --n 30                  列出被引最多的前 30 篇（預設 10，最多 200）

關鍵字用英文；多個字直接放在引號裡，例如 "option pricing"。
金鑰：讀環境變數 OPENALEX_API_KEY；沒有就停下來，不會用沒金鑰的網址查。
"""
import datetime, json, os, pathlib, re, sys, urllib.parse, urllib.request

for _s in (sys.stdout, sys.stderr):   # Windows 的主控台是 cp950，不改成 UTF-8 會當掉或變亂碼
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

ME = "python .opencode/skills/fetch-literature/scripts/search.py"
JOURNAL_PY = "python .opencode/skills/fetch-literature/scripts/journal.py"
TABLE = pathlib.Path(__file__).resolve().parent.parent / "references" / "journals.md"
OUT = pathlib.Path("literature.md")                     # 永遠寫在工作資料夾
ISSN = re.compile(r"^\d{4}-\d{3}[\dXx]$")
SELECT = "doi,title,publication_year,cited_by_count,authorships,primary_location"


def norm(name):
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"^the ", "", re.sub(r"\s+", " ", s).strip())


def journals():
    """對照表的每一列 → (刊名, ISSN, 等級)"""
    if not TABLE.exists(): sys.exit(f"找不到對照表 {TABLE}")
    out = []
    for l in TABLE.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in l.split("|")]
        if l.startswith("| ") and len(c) > 3 and ISSN.match(c[2]): out.append((c[1], c[2].upper(), c[3]))
    if not out: sys.exit(f"對照表是空的，先用 {JOURNAL_PY} lookup / add 加期刊")
    return out


def parse(argv):
    kw, journal, year, n = [], None, None, 10
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--journal": journal = argv[i + 1]; i += 2
        elif a == "--from": year = argv[i + 1]; i += 2
        elif a == "--n": n = int(argv[i + 1]); i += 2
        else: kw.append(a); i += 1
    kw = " ".join(kw).strip()
    if not kw: sys.exit(__doc__)
    if re.search(r"[一-鿿]", kw): sys.exit(f"關鍵字要用英文（OpenAlex 的論文幾乎都是英文，中文一定 0 筆）。請使用者確認英文詞再查。")
    if year and not re.fullmatch(r"\d{4}", year): sys.exit("--from 後面要接四位數年份，例如 --from 2015")
    if not 1 <= n <= 200: sys.exit("--n 要在 1 到 200 之間")
    return kw, journal, year, n


def pick(journal):
    rows = journals()
    if not journal: return rows
    j = journal.strip()
    hit = [r for r in rows if r[1] == j.upper() or norm(r[0]) == norm(j)]
    if not hit:
        names = "、".join(r[0] for r in rows)
        sys.exit(f"對照表裡沒有「{j}」。表裡現在有：{names}。\n"
                 f"要查別本，先用 {JOURNAL_PY} lookup \"刊名\" 查 ISSN 再 add 進表，不可以自己猜 ISSN。")
    return hit


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "nkust-academic-ai-agent"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429: sys.exit("OpenAlex 回應 429：今天的額度用完了，停下來告訴使用者。")
        sys.exit(f"OpenAlex 回應錯誤 {e.code}：{e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"連不上 OpenAlex：{e}")


def authors(w):
    names = [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])]
    names = [x for x in names if x]
    if not names: return "（無作者資訊）"
    return "、".join(names[:3]) + ("等" if len(names) > 3 else "")


def main():
    kw, journal, year, n = parse(sys.argv[1:])
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not key:
        sys.exit("沒有 OPENALEX_API_KEY，停下來請使用者提供金鑰（申請：https://openalex.org/settings/api），不要用沒金鑰的網址查。")
    rows = pick(journal)
    issns = "|".join(r[1] for r in rows)
    # is_core:true 只留核心期刊，排除冒名期刊；title_and_abstract.search 只比對標題與摘要，不比全文
    filt = (f"primary_location.source.issn:{issns},primary_location.source.is_core:true,"
            f"title_and_abstract.search:%22{urllib.parse.quote(kw)}%22")
    if year: filt += f",from_publication_date:{year}-01-01"
    url = f"https://api.openalex.org/works?filter={filt}&sort=cited_by_count:desc&per-page={n}&select={SELECT}"
    data = fetch(url + "&api_key=" + urllib.parse.quote(key))
    total, works = data["meta"]["count"], data["results"]
    today = datetime.date.today().isoformat()
    scope = rows[0][0] if journal else f"對照表全部 {len(rows)} 本期刊"
    cond = f"主題 {kw}｜期刊 {scope}｜{('從 ' + year + ' 年起') if year else '不限年份'}｜總筆數 {total}｜查詢日期 {today}"

    lines = [f"# 文獻清單：{kw}", "", cond, ""]
    if works:
        lines += ["| 年份 | 作者 | 標題 | 期刊 | 被引數 | DOI |", "|---|---|---|---|---|---|"]
        for w in works:
            src = (w.get("primary_location") or {}).get("source") or {}
            t = (w.get("title") or "").replace("|", "｜")
            lines.append(f"| {w.get('publication_year', '')} | {authors(w)} | {t} | {src.get('display_name', '')} | "
                         f"{w.get('cited_by_count', 0)} | {w.get('doi') or '（無 DOI）'} |")
    else:
        lines.append("查詢結果：0 筆")
    lines += ["", "查詢網址（金鑰已遮）：", url + "&api_key=***", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"期刊範圍：{scope}（ISSN {issns}）")
    print(f"查詢網址：{url}&api_key=***")
    print(f"查到 {total} 筆" + (f"，已把被引最多的前 {len(works)} 篇寫進 {OUT.resolve()}" if works else ""))
    if total == 0:
        print("\n0 筆通常不是程式錯，是「這些期刊不做這個主題」或「論文用的是別的說法」。把下面兩個建議告訴使用者，讓使用者選，不要自己換：")
        print(f"  1. 換期刊：請使用者提供他領域的期刊，用 {JOURNAL_PY} lookup / add 加進對照表再查。")
        print(f"  2. 換說法：提出 2–3 個英文同義詞，使用者挑一個再用 {ME} 查。")
    elif total < 5:
        print("\n筆數很少。交出清單時順便提醒使用者：要更多可以換說法（英文同義詞）或換期刊（加進對照表）。")
    elif total > len(works):
        print(f"\n還有 {total - len(works)} 篇沒列出；使用者要更多就加 --n（最多 200）。")


if __name__ == "__main__":
    main()
