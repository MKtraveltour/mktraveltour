"""
build_momiji.py  ―  紅葉ツアー特集ページ（momiji2026.html）の自動更新

  tour_data.json   … scraper.py が取得した日程・料金・空席（自動）
  momiji_config.json … 説明文・行程・エリアなど（手入力・任意）

  掲載されるツアー:
    ・momiji_config.json の "tours" に書いたツアー
    ・それ以外でも、tour_editor.py で「紅葉ツアー」にチェックしたツアー、
      またはタイトルに「紅葉」「もみじ」を含むツアーは自動で掲載
    ・載せたくないツアーは momiji_config.json の "exclude" にキーを書く
  ↓
  momiji2026.html の ==TOURS_START== ～ ==TOURS_END== の間だけを書き換えます。
  デザイン部分には触れません。

使い方:
  python build_momiji.py          … 更新する
  python build_momiji.py --check  … 書き換えずに内容だけ確認する
"""
import json
import os
import re
import sys
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOUR_DATA_PATH = os.path.join(BASE_DIR, "tour_data.json")
CONFIG_PATH = os.path.join(BASE_DIR, "momiji_config.json")

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

MOMIJI_TAGS = {"momiji", "紅葉", "紅葉ツアー", "🍁紅葉ツアー"}   # tour_editor.py の「紅葉ツアー」チェックで付くタグ
MOMIJI_WORDS = ("紅葉", "もみじ")


def is_momiji(td):
    """旅とも手帳側で紅葉ツアーと判断できるか（タグ または タイトル）"""
    title = td.get("title", "")
    tags = {str(t).strip() for t in (td.get("tags") or [])}
    return bool(tags & MOMIJI_TAGS) or any(w in title for w in MOMIJI_WORDS)


def build(config, tour_data, today):
    tours, notes = [], []
    conf_by_key = {c["key"]: c for c in config.get("tours", [])}
    exclude = set(config.get("exclude", []))

    # 掲載候補：① momiji_config.json に書いたツアー（その順番） ② 紅葉ツアーと判断できる残りのツアー
    order = [c["key"] for c in config.get("tours", [])]
    auto = [k for k, td in tour_data.items()
            if k not in conf_by_key and k not in exclude and is_momiji(td)]
    order += auto

    for key in order:
        c = conf_by_key.get(key, {})
        td = tour_data.get(key)
        if td is None:
            notes.append(f"⚠ {key}: tour_data.json に見つからないため掲載しません")
            continue
        if td.get("hidden"):
            notes.append(f"・{key}: 非表示設定のため掲載しません")
            continue
        title_raw = td.get("title", "")
        if "募集終了" in title_raw:
            notes.append(f"・{key}: 募集終了のため掲載しません")
            continue

        raw_dates = td.get("dates", []) or []
        parsed = [norm_date(x, today) for x in raw_dates]
        dates = sorted({d for d in parsed if d and d >= today})
        if not dates:
            if key not in conf_by_key:
                if not raw_dates:
                    notes.append(f"🕒 {key}: 紅葉ツアーとして検知しましたが、開催日がまだ取得されていません"
                                 f"（run.py でスクレイパーが動いたあとに掲載されます）→「{title_raw[:30]}」")
                elif not any(parsed):
                    notes.append(f"⚠ {key}: 紅葉ツアーとして検知しましたが、開催日を読み取れませんでした（例: {raw_dates[:3]}）")
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
            notes.append(f"🆕 {key}: 新しい紅葉ツアーとして自動で掲載しました（エリア・説明文・行程は未設定）"
                         f" →「{title_raw[:30]}」")
        if td.get("error"):
            notes.append(f"⚠ {key}: 前回の取得でエラーが出ています（前回のデータで掲載）")
        if not td.get("image") and not c.get("img"):
            notes.append(f"⚠ {key}: 画像がありません")
    return tours, notes


def fix_github_url(u):
    """github.com の写真ページURLを、表示用（raw）のURLに変える"""
    return re.sub(r"^https://github\.com/([^/]+)/([^/]+)/blob/", r"https://raw.githubusercontent.com/\1/\2/", u.strip())


def render_block(tours, area_notes, updated_at, hero_images=None):
    js = json.dumps(tours, ensure_ascii=False, indent=1).replace("</", "<\\/")
    an = json.dumps(area_notes, ensure_ascii=False)
    return (f"{START_MARK} この行から ==TOURS_END== までは更新スクリプトが自動で書き換えます */\n"
            f"var TOURS = {js};\n"
            f"var AREA_NOTES = {an};\n"
            f"var HERO_IMAGES = {json.dumps(hero_images or [], ensure_ascii=False, indent=1)};\n"
            f"var UPDATED_AT = '{updated_at}';\n"
            f"{END_MARK}")


def main(check_only=False):
    config = load_json(CONFIG_PATH)
    tour_data = load_json(TOUR_DATA_PATH)
    html_path = os.path.join(BASE_DIR, config.get("output_html", "momiji2026.html"))

    today = date.today().isoformat()
    tours, notes = build(config, tour_data, today)
    now = datetime.now()
    updated_at = f"{now.year}年{now.month}月{now.day}日 {now:%H:%M}"

    hero = [{"url": fix_github_url(h["url"]), "caption": h.get("caption", ""), "position": h.get("position", "center")}
            for h in config.get("hero_images", []) if h.get("url")]

    print(f"🍁 紅葉ページ：{len(tours)}件のツアーを掲載します（トップ写真 {len(hero)}枚）")
    for t in tours:
        print(f"   {t['statusText']:<8} {t['title'][:24]}（{len(t['dates'])}日）")
    for n in notes:
        print("   " + n)

    if check_only:
        print("（--check のため書き換えていません）")
        return 0

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    s = html.find(START_MARK)
    e = html.find(END_MARK)
    if s < 0 or e < 0:
        print(f"❌ {os.path.basename(html_path)} に ==TOURS_START== / ==TOURS_END== が見つかりません")
        return 1
    new_html = html[:s] + render_block(tours, config.get("area_notes", {}), updated_at, hero) + html[e + len(END_MARK):]

    tmp = html_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_html)
    os.replace(tmp, html_path)
    print(f"✅ {os.path.basename(html_path)} を更新しました（{updated_at}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(check_only="--check" in sys.argv))
