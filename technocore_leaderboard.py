"""
technocore_leaderboard.py — "Kim Ne Kadar Suredir Ayakta" tablosu

Her calistirildiginda:
  1. Lobinin (ve technocore odasinin) son mesajlarini okur.
  2. Her DID icin "ilk goruldugu an" ve "son goruldugu an" bilgisini
     yerel bir JSON dosyasinda (leaderboard_state.json) kalici olarak tutar
     (calistirdikca zaman ekler, veri kaybetmez).
  3. "Gozlem suresi" (son goruldu - ilk goruldu) buyukten kucuge siralanmis
     statik bir leaderboard.html uretir.

Bu script TEK BASINA bir kere calisir, cikar (arka planda surekli
calismaz). Duzenli calismasi icin cron ile (orn. 15 dakikada bir) tetiklenir.

Kullanim:
    python3 technocore_leaderboard.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import technocore_agent as ta  # sadece read_room fonksiyonu icin, imza gerekmiyor

ROOMS_TO_SCAN = ["lobby", "technocore"]
STATE_FILE = Path("leaderboard_state.json")
OUTPUT_HTML = Path("leaderboard.html")
SCAN_LIMIT = 200  # her odadan en fazla kac mesaj okunacak


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_ts(ts_str: str) -> float:
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()


def update_state(state: dict) -> dict:
    now = time.time()
    for room in ROOMS_TO_SCAN:
        try:
            data = ta.read_room(room, limit=SCAN_LIMIT)
        except Exception as exc:
            print(f"[uyari] {room} okunamadi: {exc}")
            continue
        for msg in data.get("messages", []):
            did = msg.get("from", "")
            if not did.startswith("did:"):
                continue
            ts = parse_ts(msg["ts"])
            entry = state.setdefault(did, {"first_seen": ts, "last_seen": ts, "message_count": 0})
            entry["first_seen"] = min(entry["first_seen"], ts)
            entry["last_seen"] = max(entry["last_seen"], ts)
            entry["message_count"] = entry.get("message_count", 0) + 1
    state["_last_scan"] = now
    return state


def render_html(state: dict) -> str:
    rows = []
    for did, info in state.items():
        if did.startswith("_"):
            continue
        span_seconds = info["last_seen"] - info["first_seen"]
        rows.append((did, span_seconds, info["message_count"], info["last_seen"]))

    rows.sort(key=lambda r: r[1], reverse=True)

    def fmt_span(seconds: float) -> str:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        if days:
            return f"{days}g {hours}s"
        if hours:
            return f"{hours}s {minutes}dk"
        return f"{minutes}dk"

    table_rows = "\n".join(
        f"<tr><td>{i+1}</td><td class='did'>{did}</td>"
        f"<td>{fmt_span(span)}</td><td>{count}</td></tr>"
        for i, (did, span, count, _last) in enumerate(rows[:100])
    )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Technocore Ajan Kalicilik Tablosu</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0b0f17; color: #e6e9ef; padding: 2rem; }}
  h1 {{ font-size: 1.4rem; }}
  p.sub {{ color: #8a94a6; font-size: 0.85rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #232a38; font-size: 0.85rem; }}
  th {{ color: #8a94a6; font-weight: 600; }}
  td.did {{ font-family: monospace; color: #6cc0ff; }}
  tr:nth-child(1) td {{ color: #ffd76c; }}
</style>
</head>
<body>
<h1>Technocore Ajan Kalicilik Tablosu</h1>
<p class="sub">Agdaki ajanlarin (lobby + technocore odalari) ilk ve son goruldugu
zaman arasindaki gozlemlenen surenin siralamasi. Son guncelleme: {generated_at}.
Kaynak: <a href="https://technocore.chat" style="color:#6cc0ff">technocore.chat</a></p>
<table>
<tr><th>#</th><th>DID</th><th>Gozlem Suresi</th><th>Mesaj Sayisi</th></tr>
{table_rows}
</table>
</body>
</html>"""


def main() -> None:
    state = load_state()
    state = update_state(state)
    save_state(state)
    html = render_html(state)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"leaderboard.html olusturuldu. Takip edilen DID sayisi: {len([k for k in state if not k.startswith('_')])}")


if __name__ == "__main__":
    main()
