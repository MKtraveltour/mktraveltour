"""
build_momiji.py  ―  季節のツアー特集ページ（紅葉・桜・紫陽花など）の自動更新

  tour_data.json      … scraper.py が取得した日程・料金・空席（自動）
  ○○_config.json      … 季節ごとの設定（ページの文言・色・写真・説明文・行程・エリアなど）
  season_template.html … 全季節共通のページのデザイン
  ↓
  設定ファイルの output_html に、完成したページを書き出します。

  掲載されるツアー:
    ・設定ファイルの "tours" に書いたツアー
    ・それ以外でも、設定ファイルの "detect" のタグが付いたツアー、
      または "detect" の言葉をタイトルに含むツアーは自動で掲載
    ・載せたくないツアーは "exclude" にキーを書く

使い方:
  python build_momiji.py                          … 紅葉ページ（momiji_config.json）を更新
  python build_momiji.py ajisai_config.json       … 指定した季節のページを更新
  python build_momiji.py ajisai_config.json --check … 書き換えずに内容だけ確認
"""
import json
import os
import re
import sys
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOUR_DATA_PATH = os.path.join(BASE_DIR, "tour_data.json")
DEFAULT_CONFIG = "momiji_config.json"
TEMPLATE_PATH = os.path.join(BASE_DIR, "season_template.html")

START_MARK = "/* ==TOURS_START=="
END_MARK = "/* ==TOURS_END== */"


# ---------- 読み込み ----------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- 日付・空席の整形 ----------

def norm_date(s, today=None):
    """
    いろいろな書き方の日付を 'YYYY-MM-DD' にそろえる。
      '2026-11-21' / '2026/11/21' / '2026.11.21' / '2026年11月21日'
      '11/21' / '11/21(土)' / '11月21日'  … 年がない場合は今日を基準に決める
    """
    t = str(s).strip().translate(str.maketrans("０１２３４５６７８９／", "0123456789/"))
    m = re.match(r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})", t)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"(\d{1,2})\s*[/月]\s*(\d{1,2})", t)
        if not m:
            return None
        mo, d = map(int, m.groups())
        base = date.fromisoformat(today) if today else date.today()
        y = base.year
        # 例：12月に「1/10」とあれば翌年。4か月以上前の日付は翌年とみなす
        try:
            if (base - date(y, mo, d)).days > 120:
                y += 1
        except ValueError:
            return None
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def expand_dates(raw_dates, today):
    """
    開催日のリストを 'YYYY-MM-DD' のリストにする。
    '2026年11月18日(水)～12月6日（日）' のような期間の書き方は、毎日の日付に展開する。
    """
    out = []
    for x in raw_dates or []:
        parts = re.split(r"\s*[～〜~]\s*", str(x))
        if len(parts) == 2:
            a = norm_date(parts[0], today)
            b_raw = parts[1]
            # 終わりの日付に年がなければ、始まりの年を付けて読む
            if a and not re.match(r"\s*\d{4}", b_raw):
                b = norm_date(a[:4] + "年" + b_raw, today)
                if b and b < a:
                    b = norm_date(str(int(a[:4]) + 1) + "年" + b_raw, today)
            else:
                b = norm_date(b_raw, today)
            if a and b and a <= b:
                d, e = date.fromisoformat(a), date.fromisoformat(b)
                while d <= e:
                    out.append(d.isoformat())
                    d = date.fromordinal(d.toordinal() + 1)
                continue
        out.append(norm_date(x, today))
    return out


def per_date_status(td, dates):
    """
    tour_data の statuses を {日付(YYYY-MM-DD): 種類} にする。
    scraper.py の形式: [{"date": "7/2", "type": "confirmed", "label": "催行確定"}, ...]
    "7/2" には年がないため、ツアーの開催日（dates）と月日を照らし合わせて年を決めます。
    """
    raw = td.get("statuses") or []
    by_md = {}
    for d in dates:
        y, m, dd = d.split("-")
        by_md[(int(m), int(dd))] = d

    out = {}
    items = raw.items() if isinstance(raw, dict) else [
        (x.get("date", ""), x.get("type") or x.get("label") or "") for x in raw if isinstance(x, dict)]
    for k, v in items:
        # 年なし（'7/2' など）は、開催日の中から同じ月日を探す
        m = re.match(r"\s*(\d{1,2})\s*[/月]\s*(\d{1,2})", str(k))
        d = by_md.get((int(m.group(1)), int(m.group(2)))) if m else norm_date(k)
        if d in dates:
            out[d] = str(v)
    return {d: out.get(d, "") for d in dates}


def per_date_labels(td, dates):
    """{日付: label} （「あと2名」などの人数を取り出すため）"""
    tmp = dict(td)
    tmp["statuses"] = [{"date": x.get("date", ""), "type": x.get("label", "")}
                       for x in (td.get("statuses") or []) if isinstance(x, dict)]
    return per_date_status(tmp, dates)


def classify(text):
    t = str(text)
    if "満席" in t or t == "full":
        return "full"
    if "確定" in t or t == "confirmed":
        return "confirmed"
    if "あと" in t or "残" in t or t == "few":
        return "few"
    return "open"


def summarize(statuses, labels):
    """カード左上のバッジ（全体の状況）を決める。labels は {日付: '催行まであと2名'などの表示文}"""
    kinds = {d: classify(v) for d, v in statuses.items()}
    if kinds and all(k == "full" for k in kinds.values()):
        return "full", "満席"
    if any(k == "confirmed" for k in kinds.values()):
        return "confirmed", "催行確定日あり"
    few = [labels.get(d) or "" for d, k in kinds.items() if k == "few"]
    if few:
        def remain(v):
            n = re.search(r"[0-9０-９]+", v)
            return int(n.group().translate(str.maketrans("０１２３４５６７８９", "0123456789"))) if n else 99
        best = min(few, key=remain)
        n = re.search(r"[0-9０-９]+", best)
        return "few", (f"催行まであと{n.group()}名" if n else "催行まであと少し")
    return "open", "募集中"


def parse_price(raw):
    """'大人1名 6,800円～7,800円（税込）' → (6800, '6,800円～7,800円')"""
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d{1,3}(?:,\d{3})+|\d{4,}", str(raw))]
    if not nums:
        return 0, ""
    lo, hi = min(nums), max(nums)
    text = f"{lo:,}円～{hi:,}円" if hi != lo else ""
    return lo, text


def split_title(title):
    """'本タイトル ～サブ～' を分ける（configに書いていない場合の予備）"""
    m = re.match(r"(.+?)\s*[～〜](.+?)[～〜]?\s*$", title)
    return (m.group(1).strip(), m.group(2).strip()) if m else (title.strip(), "")


# ---------- 組み立て ----------

DEFAULT_DETECT = {"tags": ["momiji", "紅葉", "紅葉ツアー", "🍁紅葉ツアー"], "words": ["紅葉", "もみじ"]}


def is_target(td, detect):
    """その季節のツアーと判断できるか（タグ または タイトルの言葉）"""
    title = td.get("title", "")
    tags = {str(t).strip() for t in (td.get("tags") or [])}
    return bool(tags & set(detect.get("tags", []))) or any(w in title for w in detect.get("words", []))


def build(config, tour_data, today, model=False):
    """
    model=True（モデルページ）のときは、【募集終了】のツアーも載せ、
    タイトルの【募集終了】を外して表示します。
    """
    tours, notes = [], []
    detect = config.get("detect", DEFAULT_DETECT)
    conf_by_key = {c["key"]: c for c in config.get("tours", [])}
    exclude = set(config.get("exclude", []))

    order = [c["key"] for c in config.get("tours", [])]
    auto = [k for k, td in tour_data.items()
            if k not in conf_by_key and k not in exclude and is_target(td, detect)]
    order += auto

    for key in order:
        c = conf_by_key.get(key, {})
        td = tour_data.get(key)
        if td is None:
            notes.append(f"・{key}: tour_data.json にありません（昨年以前のツアーなら、設定ファイルから消してOK）")
            continue
        if td.get("hidden") and not model:
            notes.append(f"・{key}: 非表示設定のため掲載しません")
            continue
        title_raw = td.get("title", "")
        if "募集終了" in title_raw:
            if not model:
                notes.append(f"・{key}: 募集終了のため掲載しません")
                continue
            title_raw = re.sub(r"【?募集終了】?\s*", "", title_raw).strip()

        raw_dates = td.get("dates", []) or []
        parsed = expand_dates(raw_dates, today)
        dates = sorted({d for d in parsed if d and d >= today})
        if not dates:
            if key not in conf_by_key:
                if not raw_dates:
                    notes.append(f"🕒 {key}: 対象ツアーとして検知しましたが、開催日がまだ取得されていません"
                                 f"（run.py でスクレイパーが動いたあとに掲載されます）→「{title_raw[:30]}」")
                elif not any(parsed):
                    notes.append(f"⚠ {key}: 対象ツアーとして検知しましたが、開催日を読み取れませんでした（例: {raw_dates[:3]}）")
            else:
                if not raw_dates:
                    notes.append(f"・{key}: tour_data.json に開催日が入っていないため掲載しません")
                elif not any(parsed):
                    notes.append(f"⚠ {key}: 開催日の書き方を読み取れませんでした（例: {raw_dates[:3]}）")
                else:
                    notes.append(f"・{key}: 今日以降の開催日がないため掲載しません（最終 {max(d for d in parsed if d)}）")
            continue

        st = per_date_status(td, dates)
        labels = per_date_labels(td, dates)
        status, status_text = summarize(st, labels)
        price, price_text = parse_price(td.get("price", ""))
        t_auto, s_auto = split_title(title_raw)

        tours.append({
            "id": key,
            "area": c.get("area") or "その他",
            "title": c.get("title") or t_auto,
            "sub": c.get("sub") or s_auto,
            "url": td.get("url", ""),
            "img": c.get("img") or td.get("image", ""),
            "desc": c.get("desc", ""),
            "price": price,
            "priceText": c.get("priceText") or price_text,
            "dates": dates,
            "confirmed": [d for d, v in st.items() if classify(v) == "confirmed"],
            "full": [d for d, v in st.items() if classify(v) == "full"],
            "status": status,
            "statusText": status_text,
            "tags": c.get("tags", []),
            "time": c.get("time", ""),
            "steps": c.get("steps", []),
        })
        if key not in conf_by_key:
            notes.append(f"🆕 {key}: 新しいツアーとして自動で掲載しました（エリア・説明文・行程は未設定）"
                         f" →「{title_raw[:30]}」")
        if td.get("error"):
            notes.append(f"⚠ {key}: 前回の取得でエラーが出ています（前回のデータで掲載）")
        if not td.get("image") and not c.get("img"):
            notes.append(f"⚠ {key}: 画像がありません")
    return tours, notes


def fix_github_url(u):
    """github.com の写真ページURLを、表示用（raw）のURLに変える"""
    return re.sub(r"^https://github\.com/([^/]+)/([^/]+)/blob/", r"https://raw.githubusercontent.com/\1/\2/", u.strip())


def js(v):
    return json.dumps(v, ensure_ascii=False, indent=1).replace("</", "<\\/")


def render_block(tours, area_notes, updated_at, hero_images=None, tag_order=None, empty=None):
    return (f"{START_MARK} この行から ==TOURS_END== までは更新スクリプトが自動で書き換えます */\n"
            f"var TOURS = {js(tours)};\n"
            f"var AREA_NOTES = {json.dumps(area_notes, ensure_ascii=False)};\n"
            f"var HERO_IMAGES = {js(hero_images or [])};\n"
            f"var SITE_TAG_ORDER = {json.dumps(tag_order or [], ensure_ascii=False)};\n"
            f"var EMPTY = {json.dumps(empty or {}, ensure_ascii=False)};\n"
            f"var UPDATED_AT = {json.dumps(updated_at, ensure_ascii=False)};\n"
            f"{END_MARK}")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def apply_year(site, year):
    """設定の文言の {year} を、そのシーズンの年に置き換える"""
    out = {}
    for k, v in site.items():
        out[k] = v.replace("{year}", str(year)) if isinstance(v, str) else v
    return out


def redirect_page(to_url, title):
    """古いページ名（例: momiji2026.html）に来た人を、新しいページへ案内する"""
    t = esc(title)
    u = esc(to_url)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={u}">
<link rel="canonical" href="{u}">
<title>{t}</title>
<script>location.replace({json.dumps(to_url)} + location.search + location.hash);</script>
</head>
<body style="font-family:sans-serif;text-align:center;padding:40px 16px;color:#4d3a29">
<p>ページが移動しました。自動で切り替わらない場合は、こちらからご覧ください。</p>
<p><a href="{u}">{t}</a></p>
</body>
</html>
"""


def render_template(site, block, model_notice):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    # テンプレート冒頭の説明コメントは出力に含めない
    html = re.sub(r"<!-- 季節特集ページのテンプレート。.*?-->\n", "", html, count=1, flags=re.S)
    values = {
        "__PAGE_TITLE__": esc(site.get("page_title", "")),
        "__DESCRIPTION__": esc(site.get("description", site.get("lead", ""))),
        "__PAGE_URL__": esc(site.get("page_url", "")),
        "__OG_IMAGE__": esc(fix_github_url(site.get("og_image", ""))),
        "__EYEBROW__": esc(site.get("eyebrow", "")),
        "__HEADLINE__": "<br>".join(esc(x) for x in str(site.get("headline", "")).split("\n")),
        "__LEAD__": esc(site.get("lead", "")),
        "__LIST_TITLE__": esc(site.get("list_title", "ツアー一覧")),
        "__FAV_KEY__": re.sub(r"[^A-Za-z0-9_]", "", site.get("fav_key", "mkSeasonFavorites")),
        "__ACCENT__": site.get("accent", "#9b3f26"),
        "__ACCENT_SOFT__": site.get("accent_soft", "#f6e1d4"),
        "__ACCENT_INK__": site.get("accent_ink", "#6e2c18"),
        "__ACCENT_MID__": site.get("accent_mid", "#ecc7b4"),
        "__ROBOTS__": '<meta name="robots" content="noindex">' if model_notice else "",
        "__NOTICE__": f'<div class="model-notice">{esc(model_notice)}</div>' if model_notice else "",
        "__DATA_BLOCK__": block,
    }
    for k, v in values.items():
        html = html.replace(k, v)
    left = re.findall(r"__[A-Z_]+__", html)
    if left:
        print(f"⚠ テンプレートに未設定の項目があります: {sorted(set(left))}")
    return html


def main(check_only=False, config_name=None):
    config_name = config_name or DEFAULT_CONFIG
    config = load_json(os.path.join(BASE_DIR, config_name))
    tour_data = load_json(TOUR_DATA_PATH)
    html_path = os.path.join(BASE_DIR, config.get("output_html", "momiji2026.html"))
    site = config.get("site")
    model = config.get("model") or {}
    label = (site or {}).get("label", "紅葉")

    # モデルページは「その時点で見たらどう見えるか」を作るため、基準日を差し替える
    today = model.get("as_of") or date.today().isoformat()
    tours, notes = build(config, tour_data, today, model=bool(model))
    now = datetime.now()
    updated_at = model.get("updated_label") or f"{now.year}年{now.month}月{now.day}日 {now:%H:%M}"

    hero = [{"url": fix_github_url(h["url"]), "caption": h.get("caption", ""), "position": h.get("position", "center")}
            for h in config.get("hero_images", []) if h.get("url")]

    print(f"🗂 {label}ページ（{config_name}）：{len(tours)}件のツアーを掲載します（トップ写真 {len(hero)}枚）"
          + ("　※モデルページ" if model else ""))
    for t in tours:
        print(f"   {t['statusText']:<8} {t['title'][:24]}（{len(t['dates'])}日）")
    for n in notes:
        print("   " + n)

    if check_only:
        print("（--check のため書き換えていません）")
        return 0

    tag_order = (site or {}).get("tag_order", ["早朝", "夜のライトアップ", "食事付き", "半日", "限定貸切"])
    # シーズンの年：掲載ツアーの最初の開催日の年（ツアーがなければ今年）
    year = int(min(t["dates"][0] for t in tours)[:4]) if tours else int(today[:4])
    if site:
        site = apply_year(site, year)
    empty = (site or {}).get("empty", {})
    block = render_block(tours, config.get("area_notes", {}), updated_at, hero, tag_order, empty)

    if site and os.path.exists(TEMPLATE_PATH):
        # テンプレートから毎回ページ全体を作り直す
        new_html = render_template(site, block, model.get("notice", ""))
    else:
        # 旧方式：既存ページの目印の間だけを書き換える
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        s = html.find(START_MARK)
        e = html.find(END_MARK)
        if s < 0 or e < 0:
            print(f"❌ {os.path.basename(html_path)} に ==TOURS_START== / ==TOURS_END== が見つかりません")
            return 1
        new_html = html[:s] + block + html[e + len(END_MARK):]

    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    # 古いページ名からの案内ページ（Instagramなどに貼った古いリンク用）
    for old in config.get("redirect_from", []):
        old_path = os.path.join(BASE_DIR, old)
        to_url = (site or {}).get("page_url") or os.path.basename(html_path)
        with open(old_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(redirect_page(to_url, (site or {}).get("page_title", "")))
    tmp = html_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_html)
    os.replace(tmp, html_path)
    print(f"✅ {os.path.relpath(html_path, BASE_DIR)} を更新しました（{updated_at}）")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(check_only="--check" in sys.argv, config_name=args[0] if args else None))
