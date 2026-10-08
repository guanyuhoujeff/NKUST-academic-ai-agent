"""逐篇初篩：由程式一篇一篇把文獻卡摘錄送給模型判斷，模型沒有機會用關鍵字或迴圈偷懶。

只用 Python 內建模組（urllib），直接呼叫 Ollama Cloud 的 API。
key 依序從環境變數 OLLAMA_API_KEY、工作資料夾的 .ollama_key 檔讀取。
"""
import json, os, pathlib, re, time, urllib.request, urllib.error

API = "https://ollama.com/api/chat"
MODEL = "gpt-oss:120b"
KEY_FILE = pathlib.Path(".ollama_key")

SYSTEM = """你是文獻初篩助手。你會拿到一個研究問題，和一篇論文的文獻卡摘錄，判斷這篇論文能不能放進這個研究問題的文獻回顧。

判斷標準：
- 相關：這篇論文研究的對象和研究問題的【每一個關鍵概念】都對得上（例如問題問「A 如何影響 B」，這篇就要同時研究 A 和 B），或它提出的方法、資料是專門為這個問題設計的。
- 不相關：只對上一部分（例如問題問 A 對 B，這篇研究的是 A 對 C，或只研究 B 沒有 A），或主題完全不同。
- 真的拿不定，判相關，並在理由寫出疑點；第二輪讀全文時還會再篩一次。

理由要具體：說出這篇研究什麼（用摘錄裡的內容），和研究問題對得上或對不上的地方。
判「相關」時，理由裡要附摘錄中出現過的頁碼，寫成「第 N 頁」。
一律使用台灣繁體中文。

只回傳一個 JSON 物件，不要其他文字，格式固定是：
{"verdict": "相關", "reason": "理由"}
verdict 只能是 "相關" 或 "不相關"。"""

def api_key():
    k = os.environ.get("OLLAMA_API_KEY", "").strip()
    if not k and KEY_FILE.exists(): k = KEY_FILE.read_text(encoding="utf-8").strip()
    return k

def parse(msg):
    """模型常把 JSON 包在 ```json 裡或前後加話；抓出第一個 {...} 再解析，欄位不對就丟 ValueError"""
    m = re.search(r"\{.*\}", msg, re.S)
    if not m: raise ValueError("沒有 JSON")
    raw = json.loads(m.group(0))
    d = {"verdict": raw.get("verdict", raw.get("判斷")), "reason": raw.get("reason", raw.get("理由"))}   # 模型常把欄位名翻成中文
    if d.get("verdict") not in ("相關", "不相關") or not d.get("reason"): raise ValueError("欄位不對")
    return d

def ask(key, question, card_excerpt, feedback="", model=MODEL, timeout=180):
    """回傳 (verdict, reason)；網路或額度問題丟 RuntimeError，訊息是給人看的中文"""
    user = f"研究問題：{question}\n\n文獻卡摘錄：\n{card_excerpt}"
    if feedback: user += f"\n\n你上一次的回答有問題：{feedback}\n請修正後重新回答。"
    body = json.dumps({"model": model, "stream": False, "think": "low",
                       "options": {"temperature": 0},
                       "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(API, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                msg = json.loads(r.read().decode("utf-8"))["message"]["content"]
            d = parse(msg)
            return d["verdict"], " ".join(str(d["reason"]).split())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code == 401: raise RuntimeError("Ollama 的 key 不對（401）。請使用者確認 key 有沒有貼錯。")
            if "usage limit" in detail: raise RuntimeError(f"這把 key 的用量到上限了：{detail}")
            if e.code == 429 or e.code >= 500:
                time.sleep(5 * (attempt + 1)); continue
            raise RuntimeError(f"Ollama API 錯誤 {e.code}：{detail}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2: raise RuntimeError(f"連不上 Ollama：{e}")
            time.sleep(5)
        except (ValueError, KeyError):
            if attempt == 2: raise RuntimeError("模型連續三次沒有回傳正確的 JSON")
    raise RuntimeError("Ollama 一直忙線（429／5xx），過一分鐘再試")
