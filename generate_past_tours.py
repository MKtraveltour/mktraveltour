# -*- coding: utf-8 -*-
"""
generate_past_tours.py  ― 催行済みツアー 月別一覧 (past_tours.html) の自動生成

  管理表(Googleスプレッドシート) → 催行日から月を判定 → past_tours.html
  ・認証はサービスアカウント（非公開のまま・読み取り専用・A〜F列だけを取得）
  ・スプレッドシートに繋がらない時は、予備のExcelで代用
  ・単体実行:  python generate_past_tours.py     （run.py からも呼ばれる）
"""
import os, re, sys, json, datetime, collections
from html import escape

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUT_PATH   = os.path.join(BASE_DIR, "past_tours.html")
CACHE_PATH = os.path.join(BASE_DIR, "past_link_cache.json")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")      # archive_tours.py が保存した開催年別のページ
SITE_BASE  = "https://travel.mk-group.co.jp/tourkyoto/"

# ================= 設定 =================
# 【Excel方式】管理表(Googleスプレッドシート)を .xlsx でダウンロードして、下のフォルダに入れる。
#   ・フォルダ内で「一番新しい .xlsx」を自動で使う（ファイル名はそのままでOK）
#   ・リポジトリ(Z:\mktravel)の「外」に置くこと（run.py は git add -A で公開リポジトリに送るため）
EXCEL_DIR        = os.environ.get("MK_EXCEL_DIR", os.path.join(os.path.dirname(BASE_DIR), "mktravel_private"))
EXCEL_SHEET_NAME = ""     # 空なら、見出し(ツアー名・催行日)から管理表のタブを自動判定
STALE_DAYS       = 14     # Excelがこの日数より古いと警告を出す
SHOW_BACK_BUTTON = True   # 「MKトラベル手帳に戻る」ボタン（index.htmlと同じ場所に置く場合）
CHECK_LINKS      = True   # 公式サイトに実在するページだけをリンクにする

# 【スプレッドシート直接読み込み】使わない場合は空のままでOK（サービスアカウント方式）
SPREADSHEET_ID = ""
SHEET_NAME     = ""
KEY_PATH       = os.environ.get("MK_SA_KEY", r"C:\mktravel_secrets\service_account.json")
# =======================================

TEMPLATE = r'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>催行済みツアー 月別一覧 | MKトラベル</title>
<style>
  :root { --bg:#faf8f5; --card:#fff; --text:#3c2e1e; --sub:#8a7a66; --line:#e0d8cc; --brand:#8b7355; --brand-dark:#6b5842; --link:#7a4a1e; --chip:#f0e8d8; --yr:#efe6d6; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#1c1a17; --card:#26231f; --text:#efe8dc; --sub:#a8977f; --line:#3a3530; --brand:#b09a78; --brand-dark:#c8b290; --link:#e3b98a; --chip:#332e27; --yr:#3a342b; } }
  :root[data-theme="dark"] { --bg:#1c1a17; --card:#26231f; --text:#efe8dc; --sub:#a8977f; --line:#3a3530; --brand:#b09a78; --brand-dark:#c8b290; --link:#e3b98a; --chip:#332e27; --yr:#3a342b; }
  * { box-sizing:border-box; margin:0; padding:0; }
  html { scroll-behavior:smooth; }
  :root { padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px); }
  body { font-family:'Noto Sans JP',sans-serif; background:var(--bg); color:var(--text); }
  header { background:#8b7355; color:#fff; padding:18px 24px; }
  header h1 { font-size:18px; font-weight:500; }
  header p { font-size:12px; opacity:.85; margin-top:2px; }
  .hero { background:linear-gradient(135deg,#5c4a32,#8b7355); color:#fff; padding:32px 24px; text-align:center; }
  .hero h2 { font-size:22px; font-weight:500; margin-bottom:8px; }
  .hero p { font-size:13px; opacity:.9; line-height:1.7; }
  .count { display:inline-block; background:rgba(255,255,255,.2); border-radius:20px; padding:4px 16px; font-size:13px; margin-top:12px; }
  .nav { display:flex; gap:8px; justify-content:center; flex-wrap:wrap; margin:22px auto 0; padding:0 16px; max-width:1100px; }
  .nav a { background:var(--chip); color:var(--text); border:1px solid var(--line); border-radius:999px; padding:6px 14px; font-size:13px; font-weight:500; text-decoration:none; }
  .nav a small { font-size:10px; margin-left:5px; color:var(--brand); }
  .nav a:hover { border-color:var(--brand); }
  .legend { max-width:1100px; margin:14px auto 0; padding:0 20px; font-size:11px; color:var(--sub); text-align:center; line-height:1.8; }
  .legend b { color:var(--link); }
  .container { max-width:1100px; margin:8px auto 0; padding:0 20px; }
  section { scroll-margin-top:12px; margin-top:26px; }
  .month-title { font-size:17px; font-weight:500; border-left:5px solid var(--brand); padding-left:12px; margin-bottom:10px; display:flex; align-items:baseline; gap:10px; }
  .month-title span { font-size:12px; color:var(--brand); font-weight:400; }
  .list { list-style:none; display:grid; grid-template-columns:1fr 1fr; gap:6px 18px; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 16px; }
  .list li { display:flex; align-items:baseline; gap:8px; font-size:12.5px; line-height:1.6; padding:3px 0; border-bottom:1px dashed var(--line); }
  .yr { flex:0 0 auto; background:var(--yr); color:var(--sub); border-radius:4px; padding:0 6px; font-size:10.5px; font-weight:500; }
  .list a { color:var(--link); text-decoration:none; }
  .list a:hover { text-decoration:underline; }
  .nolink span:not(.yr) { color:var(--sub); }
  .note { flex:0 0 auto; font-size:10.5px; color:var(--sub); }
  .back { display:block; text-align:center; margin:36px auto; padding:14px 40px; background:var(--brand); color:#fff; border-radius:8px; font-size:14px; text-decoration:none; max-width:280px; }
  .back:hover { background:var(--brand-dark); }
  @media(max-width:720px) { .list { grid-template-columns:1fr; } .hero h2 { font-size:19px; } }
  :root { --onb:#fff; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --onb:#1c1a17; } }
  :root[data-theme="dark"] { --onb:#1c1a17; }
  .yfilter { max-width:1100px; margin:16px auto 0; padding:0 16px; display:flex; gap:8px; justify-content:center; align-items:center; flex-wrap:wrap; }
  .yfilter .lab { font-size:12px; color:var(--sub); margin-right:2px; }
  .yf { font:inherit; font-size:13px; font-weight:500; background:var(--card); color:var(--text); border:1px solid var(--line); border-radius:999px; padding:6px 14px; cursor:pointer; }
  .yf small { font-size:10px; margin-left:5px; color:var(--brand); }
  .yf:hover { border-color:var(--brand); }
  .yf[aria-pressed="true"] { background:var(--brand); border-color:var(--brand); color:var(--onb); }
  .yf[aria-pressed="true"] small { color:var(--onb); opacity:.85; }
  .fnote { max-width:1100px; margin:8px auto 0; padding:0 20px; font-size:11px; color:var(--sub); text-align:center; }
  .nav a.off { opacity:.3; pointer-events:none; }
  .arc-badge { flex:0 0 auto; font-size:10px; color:var(--brand); border:1px solid var(--brand); border-radius:4px; padding:0 5px; }
</style>
</head>
<body>
<header><h1>MKトラベル手帳</h1><p>MKが案内する、ここだけの京都</p></header>
<div class="hero">
  <h2>催行済みツアー 月別一覧</h2>
  <p>これまでに催行したタクシーツアーを、月ごとにご紹介します。<br>同じツアーを別の年に催行した場合は、年ごとに掲載しています。</p>
  <span class="count" id="total-count">@@TOTAL@@</span>
</div>
<nav class="nav">@@NAV@@</nav>
<div class="yfilter" id="yfilter" role="group" aria-label="年で絞り込み"><span class="lab">年で絞り込み</span></div>
<p class="fnote">年は複数選べます。随時・毎週運行は年の指定がないため、絞り込み中は表示されません。</p>
<p class="legend"><b>青字</b>＝リンクあり（公式サイトの過去ツアー一覧に掲載中のページ）／ グレー＝リンクなし<br>複数の月にまたがるツアーは、催行した各月に掲載しています。<br><span class="arc-badge">保存版</span>＝当時の内容を保存したページ（公式ページが上書きされても残ります）</p>
<div class="container">@@SECTIONS@@
  @@BACK@@
</div>
<script>
(function () {
  var secs = Array.prototype.slice.call(document.querySelectorAll('section'));
  var chips = {};
  Array.prototype.forEach.call(document.querySelectorAll('.nav a'), function (a) { chips[a.getAttribute('href').slice(1)] = a; });
  var counts = {};
  Array.prototype.forEach.call(document.querySelectorAll('.list li .yr'), function (y) { counts[y.textContent] = (counts[y.textContent] || 0) + 1; });
  var years = Object.keys(counts).sort().reverse();
  var bar = document.getElementById('yfilter');
  var sel = {};
  var btns = {};
  function btn(label, small, key) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'yf'; b.setAttribute('aria-pressed', 'false');
    b.innerHTML = label + (small !== '' ? '<small>' + small + '</small>' : '');
    b.addEventListener('click', function () {
      if (key === 'all') { sel = {}; } else if (sel[key]) { delete sel[key]; } else { sel[key] = true; }
      apply();
    });
    bar.appendChild(b);
    return b;
  }
  btns.all = btn('すべて', '', 'all');
  years.forEach(function (y) { btns[y] = btn(y + '年', counts[y], y); });
  function apply() {
    var any = Object.keys(sel).length > 0, total = 0;
    btns.all.setAttribute('aria-pressed', any ? 'false' : 'true');
    years.forEach(function (y) { btns[y].setAttribute('aria-pressed', sel[y] ? 'true' : 'false'); });
    secs.forEach(function (s) {
      var n = 0;
      Array.prototype.forEach.call(s.querySelectorAll('li'), function (li) {
        var y = li.querySelector('.yr');
        var show = !any || (y && sel[y.textContent]);
        li.style.display = show ? '' : 'none';
        if (show) n++;
      });
      total += n;
      s.style.display = n ? '' : 'none';
      var c = s.querySelector('.month-title span');
      if (c) c.textContent = n + '件';
      var chip = chips[s.id];
      if (chip) { chip.classList.toggle('off', !n); var sm = chip.querySelector('small'); if (sm) sm.textContent = n; }
    });
    var t = document.getElementById('total-count');
    if (t) t.textContent = (any ? '該当 ' : '全 ') + total + ' 件';
  }
  var yp = new URLSearchParams(location.search).get('y');
  if (yp) { years.forEach(function (y) { if (yp === '2024' ? Number(y) <= 2024 : y === yp) { sel[y] = true; } }); }
  apply();
})();
</script>
</body>
</html>'''

WD = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
WDP = r"(?:\s*[（(]([月火水木金土日祝])[^）)]*[）)])?"
SEP = r"[～~〜\-ー－]"
EXPL = re.compile(r"(20\d{2})[/.年](\d{1,2})[/.月](\d{1,2})日?" + WDP +
                  r"(?:\s*" + SEP + r"\s*(?:(\d{1,2})[/月])?(\d{1,2})日?" + WDP + r")?")
RANGE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])" + WDP +
                   r"(?:\s*[～~〜]\s*(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])" + WDP + r")?")
URL_RE = re.compile(r"https?://travel\.mk-group\.co\.jp/([^/\s]+)/([^/\s?#]+)/?")

# ---------------------------------------------------------------- 読み込み
COLS = {"fin": ("終了", 0), "d": ("ツアー名", 3), "e": ("催行日", 4), "f": ("最終日", 5)}

def _rows_from_matrix(matrix):
    """見出し行から列を探す（見つからなければ A,D,E,F 列の位置を使う）"""
    if not matrix:
        return []
    header = matrix[0]
    idx = {}
    for key, (word, pos) in COLS.items():
        hit = [i for i, h in enumerate(header) if word in str(h)]
        idx[key] = hit[0] if hit else pos
    out = []
    for r in matrix[1:]:
        g = lambda k: r[idx[k]] if idx[k] < len(r) else None
        out.append(dict(fin=g("fin"), d=g("d"), e=g("e"), f=g("f")))
    return out

def load_from_sheet(session=None):
    """Googleスプレッドシート（読み取り専用）。取得するのは A〜F 列だけ。"""
    from urllib.parse import quote
    if not (SPREADSHEET_ID and SHEET_NAME):
        raise RuntimeError("SPREADSHEET_ID / SHEET_NAME が未設定です")
    if session is None:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        creds = service_account.Credentials.from_service_account_file(
            KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        session = AuthorizedSession(creds)
    rng = quote(f"'{SHEET_NAME}'!A:F", safe="")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{rng}"
    r = session.get(url, params={"valueRenderOption": "UNFORMATTED_VALUE",
                                 "dateTimeRenderOption": "SERIAL_NUMBER"}, timeout=30)
    if r.status_code != 200:
        hint = {403: "（シートをサービスアカウントに共有していない／Sheets APIが無効の可能性）",
                404: "（SPREADSHEET_ID かタブ名が違う可能性）"}.get(r.status_code, "")
        raise RuntimeError(f"Sheets API エラー {r.status_code}{hint}: {r.text[:150]}")
    return _rows_from_matrix(r.json().get("values", []))

def _pick_sheet(wb):
    """管理表のタブを選ぶ（指定があればそれ、なければ見出しに『ツアー名』『催行日』があるタブ）"""
    if EXCEL_SHEET_NAME and EXCEL_SHEET_NAME in wb.sheetnames:
        return wb[EXCEL_SHEET_NAME]
    for ws in wb.worksheets:
        first = next(ws.iter_rows(min_row=1, max_row=1), ())
        head = " ".join(str(c.value) for c in first if c.value is not None)
        if "ツアー名" in head and "催行日" in head:
            return ws
    return wb.active

def load_from_excel(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = _pick_sheet(wb)
    return _rows_from_matrix([list(row[:6]) for row in ws.iter_rows(values_only=True)])

def find_latest_excel(folder=None):
    folder = folder or EXCEL_DIR
    if not os.path.isdir(folder): return None
    cands = [os.path.join(folder, f) for f in os.listdir(folder)
             if f.lower().endswith(".xlsx") and not f.startswith("~$")]
    return max(cands, key=os.path.getmtime) if cands else None

# ---------------------------------------------------------------- 日付の判定
def to_date(v):
    if isinstance(v, datetime.datetime): return v.date()
    if isinstance(v, datetime.date): return v
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 30000 < v < 60000:
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(v))
    return None

def resolve(m, d, wd, L):
    """月日(+曜日)と最終日から、年つきの日付を推定する"""
    def ok(y):
        try: dt = datetime.date(y, m, d)
        except ValueError: return None
        if wd in WD and dt.weekday() != WD[wd]: return None
        return dt
    if L:
        c = [x for x in (ok(y) for y in range(L.year + 1, L.year - 4, -1)) if x]
        le = [x for x in c if x <= L + datetime.timedelta(days=7)]
        if le: return max(le), "ok"
        if c: return min(c), "ok"
        if wd in WD:                       # 曜日が合う年がない（入力ミス等）→ 曜日を無視
            for y in (L.year, L.year - 1):
                try:
                    dt = datetime.date(y, m, d)
                    if dt <= L + datetime.timedelta(days=7): return dt, "wd_mismatch"
                except ValueError:
                    pass
        return None, "unresolved"
    c = [x for x in (ok(y) for y in range(2021, 2027)) if x]
    return (c[0], "ok_nolast") if len(c) == 1 else (None, "ambiguous")

def months_between(y1, m1, y2, m2):
    out, y, m = [], y1, m1
    while (y, m) <= (y2, m2) and len(out) < 24:
        out.append((y, m)); m += 1
        if m > 12: m, y = 1, y + 1
    return out

def extract_pairs(E, L, bad, conflict):
    """催行日セルから {(年, 月)} を返す"""
    pairs = set()
    d0 = to_date(E) if not isinstance(E, str) else None
    if d0:   # セル自体が日付：Excel/スプレッドシートが入力した年を自動付与するため、年は最終日で補正
        if L:
            dt, _ = resolve(d0.month, d0.day, None, L)
            if dt:
                if dt.year != d0.year: conflict.append((d0, dt))
                return {(dt.year, dt.month)}
        return {(d0.year, d0.month)}
    txt = "" if E is None else str(E)
    txt = "\n".join(l.split("※")[0] for l in txt.split("\n"))
    def sub_expl(g):
        y, m1 = int(g.group(1)), int(g.group(2))
        m2 = int(g.group(6)) if g.group(6) else m1
        if g.group(7): pairs.update(months_between(y, m1, y + (1 if m2 < m1 else 0), m2))
        else:          pairs.add((y, m1))
        return " "
    txt = EXPL.sub(sub_expl, txt)
    txt = re.sub(r"(\d{1,2})月(\d{1,2})日", r"\1/\2", txt)
    for g in RANGE.finditer(txt):
        m1, d1, w1, m2, d2, w2 = g.groups()
        dt, st = resolve(int(m1), int(d1), w1, L)
        if st in ("wd_mismatch", "ambiguous", "unresolved"): bad.append((g.group(0), st))
        if not dt: continue
        if dt.year < 2021:
            bad.append((g.group(0), "before2021")); continue
        if m2:
            y2 = dt.year + (1 if (int(m2), int(d2)) < (int(m1), int(d1)) else 0)
            pairs.update(months_between(dt.year, dt.month, y2, int(m2)))
        else:
            pairs.add((dt.year, dt.month))
    return pairs

def build_entries(rows):
    stats = collections.Counter(); entries = {}; jiji = {}; bad = []; conflict = []
    for rw in rows:
        D = rw["d"]
        if not D: continue
        stats["総行数"] += 1
        fin = rw["fin"]
        if not (fin is True or str(fin).strip().upper() == "TRUE"):
            stats["未終了・停止中(除外)"] += 1; continue
        m = URL_RE.search(str(D))
        if not m: stats["URLなし(除外)"] += 1; continue
        if m.group(1) != "tourkyoto": stats[m.group(1) + "(除外)"] += 1; continue
        slug = m.group(2); title = str(D).split("\n")[0].strip()
        L = to_date(rw["f"]); E = rw["e"]
        pairs = extract_pairs(E, L, bad, conflict)
        Es = "" if E is None else str(E)
        if pairs:
            for (y, mo) in pairs:
                entries[(y, mo, slug, title)] = dict(y=y, m=mo, slug=slug, title=title)
        else:
            note = "随時催行" if "随時" in Es else re.sub(r"\s+", " ", Es).strip()[:20]
            jiji[(slug, title)] = dict(slug=slug, title=title, note=note)
    return stats, list(entries.values()), list(jiji.values()), bad, conflict

# ---------------------------------------------------------------- リンク確認
def _fetch_status(slug):
    """True=実在 / False=存在しない / None=判定できない（通信エラー等）"""
    import requests
    try:
        r = requests.get(SITE_BASE + slug + "/", headers={"User-Agent": "Mozilla/5.0"},
                         timeout=12, allow_redirects=True, stream=True)
        code, final = r.status_code, r.url; r.close()
    except Exception:
        return None
    if code in (404, 410): return False
    if code == 200:
        last = final.rstrip("/").split("/")[-1]
        return ("/tourkyoto/" in final and last != "tourkyoto")   # 一覧やトップへ飛ばされたら False
    return None

def check_links(slugs, fetch=_fetch_status, cache_path=CACHE_PATH, workers=8):
    from concurrent.futures import ThreadPoolExecutor
    cache = {}
    if os.path.exists(cache_path):
        try: cache = json.load(open(cache_path, encoding="utf-8"))
        except Exception: cache = {}
    todo = sorted(s for s in set(slugs) if cache.get(s) is not True)   # 実在確認済みは再確認しない
    unknown = 0
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for s, res in zip(todo, ex.map(fetch, todo)):
                if res is None: unknown += 1
                else: cache[s] = bool(res)
        json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return {s: cache.get(s) is True for s in slugs}, len(todo), unknown

# ---------------------------------------------------------------- 保存版ページの索引
def _san(s):
    return re.sub(r"[^A-Za-z0-9_\-]", "_", s)

def load_archive_index(base=None):
    """archive/<年>/<URL名>/ を集めて {(URL名, 年): 相対パス} を作る（年をまたぐツアーは両方の年に対応）"""
    base = base or ARCHIVE_DIR
    idx, exact = {}, {}
    if not os.path.isdir(base): return idx
    for ydir in sorted(os.listdir(base)):
        yp = os.path.join(base, ydir)
        if not (ydir.isdigit() and os.path.isdir(yp)): continue
        for name in sorted(os.listdir(yp)):
            mp = os.path.join(yp, name, "meta.json")
            if not (os.path.exists(mp) and os.path.exists(os.path.join(yp, name, "index.html"))): continue
            try: meta = json.load(open(mp, encoding="utf-8"))
            except Exception: continue
            rel = f"archive/{ydir}/{name}/"
            for y in meta.get("years") or [int(ydir)]:
                idx.setdefault((name, int(y)), rel)
            exact[(name, int(ydir))] = rel
    idx.update(exact)            # 開催年そのものが一致する保存を優先
    return idx

def make_arc_lookup(index):
    return lambda slug, y: index.get((_san(slug), y))

# ---------------------------------------------------------------- HTML
def build_html(ent, jiji, link_ok, show_back=True, arc=None):
    by_m = collections.defaultdict(list)
    for e in ent: by_m[e["m"]].append(e)
    def li(e, year=True):
        yr = f'<span class="yr">{e["y"]}</span>' if year else ""
        note = f'<span class="note">{escape(e["note"])}</span>' if e.get("note") else ""
        if year and arc:
            href = arc(e["slug"], e["y"])
            if href:      # その年の内容を保存したページがあれば、そちらへ（公式ページが上書きされても残る）
                return f'<li>{yr}<a href="{escape(href)}">{escape(e["title"])}</a><span class="arc-badge">保存版</span>{note}</li>'
        if link_ok(e["slug"]):
            return f'<li>{yr}<a href="{SITE_BASE}{escape(e["slug"])}/" target="_blank" rel="noopener">{escape(e["title"])}</a>{note}</li>'
        return f'<li class="nolink">{yr}<span>{escape(e["title"])}</span>{note}</li>'
    sections, chips = "", ""
    for m in range(1, 13):
        items = sorted(by_m[m], key=lambda e: (-e["y"], e["title"]))
        chips += f'<a href="#m{m}">{m}月<small>{len(items)}</small></a>'
        sections += f'''
  <section id="m{m}">
    <h3 class="month-title">{m}月のツアー<span>{len(items)}件</span></h3>
    <ul class="list">{"".join(li(e) for e in items)}</ul>
  </section>'''
    jj = sorted(jiji, key=lambda e: e["title"])
    chips += f'<a href="#mx">随時・毎週<small>{len(jj)}</small></a>'
    sections += f'''
  <section id="mx">
    <h3 class="month-title">随時・毎週運行など（月の指定なし）<span>{len(jj)}件</span></h3>
    <ul class="list">{"".join(li(e, year=False) for e in jj)}</ul>
  </section>'''
    back = ('<a href="index.html" class="back">← MKトラベル手帳に戻る</a>' if show_back
            else '<div style="height:40px"></div>')
    return (TEMPLATE.replace("@@TOTAL@@", f"全 {len(ent) + len(jj)} 件")
                    .replace("@@NAV@@", chips).replace("@@SECTIONS@@", sections).replace("@@BACK@@", back))

# ---------------------------------------------------------------- 実行
def main():
    print("  管理表を読み込み中...")
    rows, src = None, ""
    if SPREADSHEET_ID and SHEET_NAME:
        try:
            rows = load_from_sheet(); src = "Googleスプレッドシート"
        except Exception as e:
            print(f"  ⚠️ スプレッドシートを読み込めませんでした: {e}")
    if rows is None:
        path = find_latest_excel()
        if not path:
            print(f"  ⚠️ 管理表のExcel(.xlsx)が見つかりません。次のフォルダに入れてください:\n     {EXCEL_DIR}")
            print("     （past_tours.html は更新しません）"); return False
        age = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(path))).days
        try:
            rows = load_from_excel(path)
        except Exception as e:
            print(f"  ⚠️ Excelを開けませんでした（{os.path.basename(path)}）: {e}")
            print("     （past_tours.html は更新しません）"); return False
        src = f"Excel「{os.path.basename(path)}」（{age}日前に保存）"
        if age > STALE_DAYS:
            print(f"  ⚠️ このExcelは{age}日前のものです。最新の管理表をダウンロードして入れ直すと、新しい催行済みツアーが反映されます")
    stats, ent, jiji, bad, conflict = build_entries(rows)
    if not ent:
        print("  ⚠️ 月別に載せられるツアーが0件でした。past_tours.html は更新しません"); return False
    print(f"  読み込み元: {src} / {dict(stats)}")
    slugs = {e["slug"] for e in ent} | {e["slug"] for e in jiji}
    if CHECK_LINKS:
        ok_map, checked, unknown = check_links(slugs)
        link_ok = lambda s: ok_map.get(s, False)
        print(f"  リンク確認: 今回{checked}件を確認 / 判定できず{unknown}件 / リンクあり {sum(ok_map.values())}件・なし {len(ok_map) - sum(ok_map.values())}件")
        if unknown: print("  ⚠️ 判定できなかったページは、今回はリンクなしで表示します（次回の実行で再確認）")
    else:
        link_ok = lambda s: True
    arc_index = load_archive_index()
    arc = make_arc_lookup(arc_index) if arc_index else None
    if arc_index: print(f"  保存版ページ: {len(arc_index)}件（開催年別）をリンクに使います")
    open(OUT_PATH, "w", encoding="utf-8").write(build_html(ent, jiji, link_ok, SHOW_BACK_BUTTON, arc))
    print(f"  ✅ past_tours.html を生成しました（月別{len(ent)}件＋随時・毎週{len(jiji)}件）")
    if conflict: print(f"  ℹ️ 催行日の年が最終日と食い違い、最終日に合わせた行: {len(conflict)}件")
    if bad:      print(f"  ℹ️ 曜日が合わない／年を確定できなかった日付: {len(bad)}件 例: {[b[0] for b in bad[:5]]}")
    return True

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
