# -*- coding: utf-8 -*-
"""
archive_tours.py ― 公開中ツアーの内容を「開催年ごと」に保存する

  ツアーページは毎年使い回され、上書きされると前の年の内容が見られなくなる。
  そこで run.py を実行するたびに、公開中の各ツアーページを開催年別に保存しておく。
    archive/<年>/<ツアーURL名>/index.html   … 読みやすく整えた保存ページ（まとめページからリンクされる）
    archive/<年>/<ツアーURL名>/raw.html.gz  … 元のHTMLそのもの（整え方を後から直せるよう保管）
    archive/<年>/<ツアーURL名>/img/…        … 画像（差し替えられても残る）
    archive/<年>/<ツアーURL名>/meta.json    … タイトル・料金・日程・保存日など
  ・上書きされて中身が変わっても、前の開催年のフォルダには手を付けない
  ・取得に失敗したり、中身が極端に減っていたりした場合は、保存済みの内容を更新しない
"""
import os, re, gzip, json, time, hashlib, datetime, collections
from html import escape
from urllib.parse import urljoin, urlparse

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
TOUR_DATA = os.path.join(BASE_DIR, "tour_data.json")

MIN_INTERVAL_H = 20        # 同じツアーを再取得する最短間隔（時間）
SHRINK_LIMIT   = 0.5       # 本文が前回の半分未満になったら、壊れた取得とみなして更新しない
MAX_IMAGES     = 6         # 1ツアーあたり保存する本文中の画像の上限（超えた分は元のURLのまま）
MAX_IMG_BYTES  = 800000    # 画像1枚あたりの上限（超えるものは保存せず、元のURLのまま）
UA = {"User-Agent": "Mozilla/5.0"}

# ------------------------------------------------------------ 開催年の判定
WD = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
_TOKEN = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])(?:\s*[（(]([月火水木金土日祝])[^）)]*[）)])?")

def edition_years(dates, today=None):
    """日程から、そのツアーが開催される年の一覧を返す（曜日つきの日付は曜日から年を確定）"""
    today = today or datetime.date.today()
    text = "\n".join(str(d) for d in (dates or []))
    years = {int(y) for y in re.findall(r"(20\d{2})年\d{1,2}月\d{1,2}日", text)}
    text = re.sub(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", r"\2/\3", text)
    text = re.sub(r"(\d{1,2})月(\d{1,2})日", r"\1/\2", text)
    toks = list(_TOKEN.finditer(text))
    for g in toks:
        m, d, wd = int(g.group(1)), int(g.group(2)), g.group(3)
        if wd in WD:
            for y in (today.year - 1, today.year, today.year + 1):
                try: dt = datetime.date(y, m, d)
                except ValueError: continue
                if dt.weekday() == WD[wd]:
                    years.add(y); break
    if years: return sorted(years)
    md = [(int(g.group(1)), int(g.group(2))) for g in toks]
    if md and today.month >= 10 and all(m <= 3 for m, _ in md):
        return [today.year + 1]
    return [today.year]

def edition_year(dates, today=None):
    return edition_years(dates, today)[0]

_WDP = r"(?:\s*[（(]([月火水木金土日祝])[^）)]*[）)])?"
_END_TITLE = ("募集終了", "受付終了")

def _safe_date(y, m, d):
    try: return datetime.date(y, m, d)
    except ValueError: return None

def last_date(dates, today=None):
    """日程のうち一番遅い日付（読み取れなければ None）"""
    today = today or datetime.date.today()
    text = "\n".join(str(d) for d in (dates or []))
    text = "\n".join(l.split("※")[0] for l in text.split("\n"))            # 「※8/17は除外」などの注記は除く
    text = re.sub(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", r"\1#\2/\3", text)
    text = re.sub(r"(?<![\d#/])(\d{1,2})月(\d{1,2})日", r"\1/\2", text)
    year = edition_year(dates, today); prev = None; best = None
    for g in re.finditer(r"(?:(20\d{2})#)?(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])" + _WDP, text):
        y = int(g.group(1)) if g.group(1) else None
        m, d, wd = int(g.group(2)), int(g.group(3)), g.group(4)
        dt = _safe_date(y, m, d) if y else None
        if dt is None and wd in WD:
            for yy in (today.year - 1, today.year, today.year + 1):
                c = _safe_date(yy, m, d)
                if c and c.weekday() == WD[wd]: dt = c; break
        if dt is None:
            if prev and prev[0] - m >= 6: year += 1                         # 12月→1月のような年またぎ
            dt = _safe_date(year, m, d)
        if dt is None: continue
        year, prev = dt.year, (m, d)
        if best is None or dt > best: best = dt
    return best

def is_ended(t, today):
    """終了していれば理由を、していなければ空文字を返す"""
    title = t.get("title", "") or ""
    if any(w in title for w in _END_TITLE): return "募集終了の表示"
    ld = last_date(t.get("dates"), today)
    if ld and ld < today: return "日程がすべて終了"
    return ""

def _saved_in_other_year(base_dir, slug, year):
    root = os.path.join(base_dir, "archive")
    if not os.path.isdir(root): return False
    return any(y != str(year) and os.path.exists(os.path.join(root, y, slug, "meta.json")) for y in os.listdir(root))

def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_\-]", "_", s)

# ------------------------------------------------------------ 本文の取り出しと無害化
_DROP = {"script", "style", "noscript", "iframe", "form", "button", "input", "select", "textarea", "svg",
         "nav", "header", "footer", "aside", "video", "audio", "object", "embed", "link", "meta",
         "canvas", "template", "head", "title"}
_KEEP = {"p", "ul", "ol", "li", "table", "thead", "tbody", "tfoot", "tr", "dl", "dt", "dd", "caption"}
_HMAP = {"h1": "h2", "h2": "h2", "h3": "h3", "h4": "h4", "h5": "h4", "h6": "h4"}
_BLOCK = {"div", "section", "article", "main", "figure", "figcaption", "blockquote", "address", "pre", "center"}
# 「7/2 催行確定」「あと2名」のような、保存した時点の空席状況は載せない（保存後に意味を失うため）
_STATUS_LINE = re.compile(r"^\s*\d{1,2}/\d{1,2}.{0,14}(催行確定|催行まで|あと\s*[0-9０-９]+\s*名|満席|受付終了|残席|キャンセル待ち)")

def _drop_status_blocks(root):
    from bs4 import BeautifulSoup
    for t in list(root.find_all(["td", "li", "p", "dd"])):
        if t.parent is None: continue
        h = re.sub(r"<br\s*/?>", "\n", t.decode_contents(), flags=re.I)
        lines = [l.strip() for l in BeautifulSoup(h, "html.parser").get_text().split("\n") if l.strip()]
        if lines and all(_STATUS_LINE.match(l) for l in lines):
            row = t.parent
            t.decompose()
            if row is not None and row.name == "tr" and not row.find("td"):
                row.decompose()          # 中身がなくなった行（見出しだけ残る行）も取り除く

def _clean(node, base, imgs):
    from bs4 import NavigableString, Tag, Comment
    out = []
    for ch in node.children:
        if isinstance(ch, Comment): continue
        if isinstance(ch, NavigableString):
            out.append(escape(re.sub(r"[\s\u3000\xa0]+", " ", str(ch)))); continue
        if not isinstance(ch, Tag): continue
        n = (ch.name or "").lower()
        if n in _DROP: continue
        if n == "img":
            src = (ch.get("src") or "").strip()
            if not src or src.startswith("data:"):
                src = (ch.get("data-src") or ch.get("data-original") or ch.get("data-lazy-src") or "").strip()
            src = urljoin(base, src) if src else ""
            if urlparse(src).scheme not in ("http", "https"): continue
            imgs.append(src)
            out.append(f'<img src="@@IMG{len(imgs) - 1}@@" alt="{escape(ch.get("alt") or "", quote=True)}">')
            continue
        if n == "br": out.append("<br>"); continue
        inner = _clean(ch, base, imgs)
        if n in _HMAP:                  out.append(f"<{_HMAP[n]}>{inner}</{_HMAP[n]}>")
        elif n in ("b", "strong"):      out.append(f"<strong>{inner}</strong>")
        elif n in ("i", "em"):          out.append(f"<em>{inner}</em>")
        elif n in ("td", "th"):
            at = "".join(f' {a}="{int(ch.get(a))}"' for a in ("colspan", "rowspan") if str(ch.get(a, "")).isdigit())
            out.append(f"<{n}{at}>{inner}</{n}>")
        elif n in _KEEP:                out.append(f"<{n}>{inner}</{n}>")
        elif n in _BLOCK:               out.append(f"<br>{inner}<br>")
        else:                           out.append(inner)       # a / span など：中身だけ残す（リンク・属性は捨てる）
    return "".join(out)

def _tidy(h):
    for _ in range(6):
        new = re.sub(r"<(p|li|td|th|tr|ul|ol|table|tbody|thead|tfoot|dl|dt|dd|h2|h3|h4|strong|em)>(\s|<br>)*</\1>", "", h)
        if new == h: break
        h = new
    h = re.sub(r"(<br>\s*){3,}", "<br><br>", h)
    return re.sub(r"^(\s|<br>)+|(\s|<br>)+$", "", h)

def pick_content(soup):
    secs = soup.select(".p-tour-detail__content-section")
    secs = [s for s in secs if not any(p in secs for p in s.parents)]
    if secs: return secs
    for sel in (".p-tour-detail", "main", "article", "#content", "#main", "body"):
        el = soup.select_one(sel)
        if el: return [el]
    return []

def extract_body(content, base_url):
    """HTML(bytes) → (無害化した本文HTML, 画像URLの一覧)"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    imgs, parts = [], []
    for sec in pick_content(soup):
        _drop_status_blocks(sec)
        parts.append(_clean(sec, base_url, imgs))
    return _tidy("<br><br>".join(parts)), imgs, soup

# ------------------------------------------------------------ 保存ページ
PAGE = r'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>@@TITLE@@（@@YEAR@@年開催・保存版） | MKトラベル</title>
<style>
  :root { --bg:#faf8f5; --card:#fff; --text:#3c2e1e; --sub:#8a7a66; --line:#e0d8cc; --brand:#8b7355; --link:#7a4a1e; --chip:#f0e8d8; --note:#fff7e6; --noteline:#ecd9a8; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#1c1a17; --card:#26231f; --text:#efe8dc; --sub:#a8977f; --line:#3a3530; --brand:#b09a78; --link:#e3b98a; --chip:#332e27; --note:#33291a; --noteline:#5a4a2a; } }
  :root[data-theme="dark"] { --bg:#1c1a17; --card:#26231f; --text:#efe8dc; --sub:#a8977f; --line:#3a3530; --brand:#b09a78; --link:#e3b98a; --chip:#332e27; --note:#33291a; --noteline:#5a4a2a; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:'Noto Sans JP',sans-serif; background:var(--bg); color:var(--text); }
  header { background:#8b7355; color:#fff; padding:14px 24px; font-size:14px; }
  header a { color:#fff; text-decoration:none; }
  .wrap { max-width:820px; margin:0 auto; padding:20px 18px 48px; overflow-wrap:anywhere; }
  .note { background:var(--note); border:1px solid var(--noteline); border-radius:10px; padding:12px 14px; font-size:12.5px; line-height:1.8; margin-bottom:18px; }
  .note a { color:var(--link); font-weight:500; }
  h1 { font-size:21px; font-weight:500; line-height:1.5; margin:6px 0 12px; }
  .year { display:inline-block; background:var(--chip); color:var(--brand); border-radius:999px; padding:2px 12px; font-size:12px; font-weight:500; }
  .hero { width:100%; border-radius:12px; margin:8px 0 14px; display:block; }
  .meta { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 16px; margin-bottom:8px; font-size:13px; line-height:1.9; }
  .meta b { color:var(--brand); margin-right:8px; font-weight:500; }
  .meta ul { margin:2px 0 0 18px; }
  .body h2 { font-size:17px; font-weight:500; border-left:5px solid var(--brand); padding-left:10px; margin:28px 0 10px; }
  .body h3 { font-size:15px; font-weight:500; color:var(--brand); margin:20px 0 8px; }
  .body h4 { font-size:14px; font-weight:500; margin:14px 0 6px; }
  .body p { margin:8px 0; line-height:1.9; font-size:14px; }
  .body ul, .body ol { margin:8px 0 8px 22px; line-height:1.85; font-size:14px; }
  .body table { border-collapse:collapse; margin:12px 0; font-size:13px; max-width:100%; display:block; overflow-x:auto; }
  .body th, .body td { border:1px solid var(--line); padding:8px 10px; vertical-align:top; line-height:1.7; text-align:left; }
  .body th { background:var(--chip); font-weight:500; }
  .body img { max-width:100%; height:auto; border-radius:8px; margin:8px 0; }
  .btns { display:flex; gap:10px; flex-wrap:wrap; margin-top:30px; }
  .btns a { flex:1 1 220px; text-align:center; padding:13px 16px; border-radius:8px; font-size:14px; text-decoration:none; }
  .primary { background:var(--brand); color:#fff; }
  .second { border:1px solid var(--brand); color:var(--link); }
</style>
</head>
<body>
<header><a href="@@BACK@@">← 催行済みツアー一覧へ</a></header>
<div class="wrap">
  <div class="note">この内容は <b>@@SAVED@@</b> に保存した、<b>@@YEAR@@年開催分</b>のものです。日程・料金・内容は、現在の募集とは異なる場合があります。<br>最新の情報は <a href="@@OFFICIAL@@" target="_blank" rel="noopener">公式サイトのツアーページ</a> をご覧ください。</div>
  <span class="year">@@YEAR@@年開催</span>
  <h1>@@TITLE@@</h1>
  @@HERO@@
  <div class="meta">@@META@@</div>
  <div class="body">@@BODY@@</div>
  <div class="btns"><a class="second" href="@@BACK@@">催行済みツアー一覧へ戻る</a><a class="primary" href="@@OFFICIAL@@" target="_blank" rel="noopener">公式サイトのページを見る</a></div>
</div>
</body>
</html>'''

def render_page(meta, body_html, back="../../../past_tours.html"):
    metas = []
    if meta.get("price"): metas.append(f'<div><b>料金</b>{escape(meta["price"])}</div>')
    dates = [d for d in (meta.get("dates") or []) if str(d).strip()]
    if dates: metas.append("<div><b>日程</b><ul>" + "".join(f"<li>{escape(str(d))}</li>" for d in dates) + "</ul></div>")
    hero = f'<img class="hero" src="img/{escape(meta["hero"])}" alt="">' if meta.get("hero") else ""
    saved = meta["captured_at"][:10].replace("-", "年", 1).replace("-", "月", 1) + "日"
    return (PAGE.replace("@@TITLE@@", escape(meta["title"])).replace("@@YEAR@@", str(meta["year"]))
                .replace("@@SAVED@@", saved).replace("@@HERO@@", hero)
                .replace("@@META@@", "".join(metas) or "（日程・料金の記載なし）")
                .replace("@@BODY@@", body_html or "<p>（本文を取得できませんでした。公式サイトのページをご覧ください）</p>")
                .replace("@@OFFICIAL@@", escape(meta["url"], quote=True)).replace("@@BACK@@", back))

# ------------------------------------------------------------ 保存の実行
def _fetch(url):
    import requests
    r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
    return r.status_code, r.url, r.content, r.headers.get("Content-Type", "")

def _download_image(url, folder, fetch):
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"): ext = ".jpg"
    name = hashlib.md5(url.encode()).hexdigest()[:12] + ext
    path = os.path.join(folder, name)
    if os.path.exists(path): return name
    try:
        st, _, data, ctype = fetch(url)
    except Exception:
        return None
    if st != 200 or not ctype.lower().startswith("image/") or len(data) > MAX_IMG_BYTES or len(data) < 200:
        return None
    os.makedirs(folder, exist_ok=True)
    open(path, "wb").write(data)
    return name

def archive_one(key, t, fetch, today, base_dir, now):
    url = t.get("url", "")
    if t.get("error") or "/tourkyoto/" not in url: return "skip"
    last = urlparse(url).path.rstrip("/").split("/")[-1]      # ?_gl=… などの付け足しは除いてページ名を取る
    slug = safe_name(last)
    years = edition_years(t.get("dates"), today); year = years[0]
    d = os.path.join(base_dir, "archive", str(year), slug)
    meta_path = os.path.join(d, "meta.json")
    prev = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else None
    reason = is_ended(t, today)
    if reason and prev:                       # 終了したツアーは、保存済みの内容をこれ以上更新しない（固定）
        if not prev.get("frozen"):
            prev.update(frozen=True, frozen_reason=reason, frozen_at=now.date().isoformat())
            json.dump(prev, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return "frozen"
    if reason and not prev and _saved_in_other_year(base_dir, slug, year):
        return "ended_dup"                    # 終了後のページを、別の年のツアーとして保存し直さない
    if prev and (now - datetime.datetime.fromisoformat(prev["captured_at"])).total_seconds() / 3600 < MIN_INTERVAL_H:
        return "recent"
    try:
        status, final, content, _ = fetch(url)
    except Exception:
        return "neterr"
    if status != 200: return "http"
    if urlparse(final).path.rstrip("/").split("/")[-1] != last: return "redirect"   # 別ページへの転送（旧URLなど）は保存しない
    body, imgs, soup = extract_body(content, final)
    from bs4 import BeautifulSoup
    text_len = len(BeautifulSoup(body, "html.parser").get_text())
    if text_len < 80: return "empty"
    if prev and prev.get("text_len") and text_len < prev["text_len"] * SHRINK_LIMIT: return "shrunk"
    img_dir = os.path.join(d, "img")
    hero_url = t.get("image") or ((soup.find("meta", property="og:image") or {}).get("content") or "")
    hero = _download_image(urljoin(final, hero_url), img_dir, fetch) if hero_url else None
    for i, u in enumerate(imgs):
        name = _download_image(u, img_dir, fetch) if i < MAX_IMAGES else None
        body = body.replace(f"@@IMG{i}@@", f"img/{name}" if name else escape(u, quote=True))
    title = t.get("title") or ((soup.find("h1") or soup.find("title") or {}).get_text(strip=True) if soup else "") or last
    title = re.sub(r"^\s*[【\[](募集終了|受付終了)[】\]]\s*", "", title) or title    # 保存ページには「募集終了」の表示を持ち込まない
    meta = dict(slug=slug, key=key, year=year, years=years, title=title, price=t.get("price", ""),
                dates=t.get("dates", []), url=url, captured_at=now.isoformat(timespec="seconds"),
                text_len=text_len, hero=hero or "")
    if reason: meta.update(frozen=True, frozen_reason=reason, frozen_at=now.date().isoformat())   # 初めて見た時点で終了済み
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "raw.html.gz"), "wb").write(gzip.compress(content, mtime=0))
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(render_page(meta, body))
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)   # 最後に書く＝保存完了の印
    return "updated" if prev else "saved"

LABELS = {"saved": "新規保存", "updated": "更新", "recent": "最近保存済み(スキップ)", "skip": "対象外",
          "frozen": "終了済みのため固定(更新せず)", "ended_dup": "終了ページ(別の年に保存済みのため保存せず)",
          "neterr": "通信エラー", "http": "ページを取得できず", "redirect": "別ページへ転送(保存せず)",
          "empty": "本文が取れず(保存せず)", "shrunk": "本文が大きく減っていたため更新せず"}

def main(tour_data_path=None, fetch=None, today=None, sleep=0.4, base_dir=None):
    tour_data_path = tour_data_path or TOUR_DATA
    base_dir = base_dir or BASE_DIR
    if not os.path.exists(tour_data_path):
        print("  ⚠️ tour_data.json が見つかりません"); return False
    tours = json.load(open(tour_data_path, encoding="utf-8"))
    fetch = fetch or _fetch
    today = today or datetime.date.today(); now = datetime.datetime.now()
    stats = collections.Counter(); problems = []
    for key, t in tours.items():
        r = archive_one(key, t, fetch, today, base_dir, now)
        stats[r] += 1
        if r in ("neterr", "http", "redirect", "empty", "shrunk"): problems.append((key, LABELS[r]))
        if r in ("saved", "updated") and sleep: time.sleep(sleep)
    print("  開催内容の保存: " + " / ".join(f"{LABELS[k]} {v}件" for k, v in stats.items() if k != "skip"))
    for k, m in problems[:8]: print(f"     ・{k}: {m}")
    return True

if __name__ == "__main__":
    main()
