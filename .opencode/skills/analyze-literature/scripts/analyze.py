#!/usr/bin/env python3
"""把一篇 PDF 交給 NotebookLM 分析，產出文獻卡。
用法:
  python analyze.py papers/某篇.pdf                                   # 用 references/main_prompt.md → notes/某篇.md
  python analyze.py papers/某篇.pdf --prompt references/did_prompt.md # 用其他 prompt → notes/某篇.did.md
同一篇 PDF 第二次分析時沿用第一次建立的 notebook（記在 notes/某篇.json），不重新上傳。
"""
import json, subprocess, sys, datetime, pathlib, argparse, importlib.util, shutil

HERE = pathlib.Path(__file__).resolve().parent
# 優先用「跑這支程式的 Python」裡裝的 nlm（不依賴 PATH）；沒有的話退回 PATH 上的 nlm
if importlib.util.find_spec("notebooklm_tools"):
    NLM = [sys.executable, "-m", "notebooklm_tools.cli.main"]
elif shutil.which("nlm"):
    NLM = ["nlm"]
else:
    sys.exit("找不到 nlm。請先安裝：python -m pip install --user notebooklm-mcp-cli")

def nlm(*args, timeout=600, cleanup=None):
    r = subprocess.run([*NLM, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        if cleanup:   # 上傳失敗時，把剛建立的空 notebook 刪掉，不留垃圾
            subprocess.run([*NLM, "notebook", "delete", cleanup, "--confirm"], capture_output=True, text=True, timeout=120)
        sys.exit(f"nlm {' '.join(args[:3])} 失敗：{(r.stderr or r.stdout).strip()[:500]}")
    return r.stdout

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--prompt", default=str(HERE.parent / "references" / "main_prompt.md"))
    ap.add_argument("--cleanup", action="store_true", help="分析完就刪掉 notebook（篇數多、怕超過筆記本上限時用）")
    a = ap.parse_args()
    pdf, prompt_file = pathlib.Path(a.pdf), pathlib.Path(a.prompt)
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        sys.exit(f"找不到 PDF：{pdf}")
    if not prompt_file.exists():
        sys.exit(f"找不到 prompt：{prompt_file}")
    prompt = prompt_file.read_text(encoding="utf-8")
    tag = prompt_file.stem.removesuffix("_prompt")           # main_prompt → main
    out = pathlib.Path("notes"); out.mkdir(exist_ok=True)
    js = out / (pdf.stem + ".json")                           # 第一次分析留下的 notebook 紀錄
    md = out / (pdf.stem + (".md" if tag == "main" else f".{tag}.md"))

    if js.exists() and (nb := json.loads(js.read_text(encoding="utf-8")).get("notebook")):
        nb_id, nb_url = nb["notebook_id"], nb.get("url", "")
        print(f"沿用既有 notebook：{nb_id}")
    else:
        nb = json.loads(nlm("notebook", "create", "lit-" + pdf.stem, "--json"))
        nb_id, nb_url = nb["notebook_id"], nb.get("url", "")
        print(f"notebook 已建立：{nb_id}")
        nlm("source", "add", nb_id, "--file", str(pdf), "--wait", "--json", cleanup=nb_id)
        print("PDF 已上傳並處理完成")

    print(f"用 {prompt_file.name} 提問（約 1–3 分鐘）…")
    q = json.loads(nlm("notebook", "query", nb_id, prompt, "--json", timeout=900))

    record = json.loads(js.read_text(encoding="utf-8")) if js.exists() else {}
    if a.cleanup:
        nlm("notebook", "delete", nb_id, "--confirm")
        print("notebook 已刪除（--cleanup）")
        nb_url = "（分析後已刪除）"
    record["notebook"] = None if a.cleanup else {"notebook_id": nb_id, "url": nb_url}
    record.setdefault("queries", {})[tag] = q
    js.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    refs = q.get("references") or []
    lines = ["---", f"source_pdf: {pdf.name}", f"prompt: {prompt_file.name}", f"notebook: {nb_url}",
             f"analyzed: {datetime.date.today()}", "generated_by: NotebookLM（經 nlm CLI）", "---", "",
             q["answer"].rstrip(), ""]
    if refs:
        lines += ["---", "", "## 附錄：引用的原文片段", ""]
        for r in refs:
            txt = " ".join((r.get("cited_text") or "").split())
            lines += [f"[{r.get('citation_number')}] {txt[:300]}", ""]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"完成：{md}（{len(q['answer'])} 字，{len(refs)} 筆引用）")

if __name__ == "__main__":
    main()
