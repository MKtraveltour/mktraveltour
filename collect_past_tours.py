# -*- coding: utf-8 -*-
"""
collect_past_tours.py  ―  過去のツアーを「保存版（archive/）」に取り込む

  past_tours.html（催行済みツアーの一覧）から、テーマ（桜・紫陽花・紅葉など）と年で
  ツアーを選び、公式ページを読み込んで archive/<年>/<ページ名>/ に保存します。

  ・読み込みは scraper.py、保存は archive_tours.py（run.py の STEP 3.7 と同じ処理）を使います。
    保存されたツアーは、past_tours.html の「保存版」や、季節ページのモデルに使われます。
  ・すでに保存版があるツアーは取り込みません（上書きしません）。
  ・公式ページが別の年の内容に更新されていた場合は、年が合わないので取り込みません。

起動: 過去ツアー編集.bat（または python collect_past_tours.py）
"""
import datetime
import glob
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAST_TOURS_HTML = os.path.join(BASE_DIR, "past_tours.html")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")

THEME_NAMES = {"sakura": "🌸 桜", "ajisai": "💠 紫陽花", "momiji": "🍁 紅葉", "food": "🍽️ 食"}


# ------------------------------------------------------------ 一覧の読み込み
def slug_of(url):
    return re.sub(r"[^A-Za-z0-9_\-]", "_", urlparse(url).path.rstrip("/").split("/")[-1])


def read_past_list():
    """past_tours.html の各ツアーを [{year, themes, title, url, slug, archived}] で返す"""
    if not os.path.exists(PAST_TOURS_HTML):
        print("⚠️ past_tours.html が見つかりません。先に run.py を実行してください。")
        return []
    with open(PAST_TOURS_HTML, encoding="utf-8") as f:
        h = f.read()
    items, seen = [], set()
    for li in re.findall(r"<li\b[^>]*>.*?</li>", h, re.S):
        y = re.search(r'class="yr">(\d{4})<', li)
        a = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', li, re.S)
        if not (y and a):
            continue
        th = re.search(r'data-th="([^"]*)"', li)
        url = a.group(1)
        title = re.sub(r"<[^>]+>", "", a.group(2)).strip()
        k = (y.group(1), slug_of(url))
        if k in seen:
            continue          # 一覧の中で同じツアーが2回出てくることがある
        seen.add(k)
        items.append({
            "year": int(y.group(1)),
            "themes": th.group(1).split() if th else [],
            "title": title,
            "url": url,
            "slug": k[1],
            "archived": url.startswith("archive/") or "arc-badge" in li,
        })
    return items


def archived_meta(year=None):
    """archive/ に保存済みのツアー（meta.json）を返す"""
    out = []
    pattern = os.path.join(ARCHIVE_DIR, str(year) if year else "*", "*", "meta.json")
    for p in sorted(glob.glob(pattern)):
        try:
            with open(p, encoding="utf-8") as f:
                m = json.load(f)
            m["_dir"] = os.path.dirname(p)
            out.append(m)
        except Exception:
            pass
    return out


def is_saved(year, slug):
    return os.path.exists(os.path.join(ARCHIVE_DIR, str(year), slug, "meta.json"))


# ------------------------------------------------------------ 取り込み
def collect_one(url, year, title_hint=""):
    """1ツアーを読み込んで archive/ に保存する。戻り値は結果の説明"""
    import scraper
    import archive_tours

    slug = slug_of(url)
    if "/tourkyoto/" not in url:
        return "公式ツアーページのURLではないため対象外"
    if is_saved(year, slug):
        return "保存済み（スキップ）"

    t = scraper.scrape_tour(slug, url)
    if t.get("error"):
        return f"読み込めませんでした（{t['error']}）"

    # 公式ページが別の年の内容に変わっていないか確認する
    today = datetime.date.today()
    page_year = archive_tours.edition_year(t.get("dates"), today, url)
    if page_year != year:
        return (f"ページの開催年が {page_year}年 になっています。"
                f"{year}年の内容ではない可能性があるため取り込みません")

    now = datetime.datetime.now()
    r = archive_tours.archive_one(slug, t, archive_tours._fetch, today, BASE_DIR, now)
    return archive_tours.LABELS.get(r, r)


def collect_by_theme(theme, year):
    items = [i for i in read_past_list() if theme in i["themes"] and i["year"] == year]
    if not items:
        print(f"  {THEME_NAMES.get(theme, theme)} {year}年 のツアーは past_tours.html にありません。")
        return
    todo = [i for i in items if not i["archived"] and not is_saved(year, i["slug"])]
    print(f"\n  {THEME_NAMES.get(theme, theme)} {year}年：{len(items)}件（未保存 {len(todo)}件）")
    for i in items:
        mark = "保存済" if i not in todo else "未保存"
        print(f"   [{mark}] {i['title'][:40]}")
    if not todo:
        print("  すべて保存済みです。")
        return
    if input(f"\n  未保存の {len(todo)}件を取り込みますか？ (y/n) > ").strip().lower() != "y":
        return
    for i in todo:
        print(f"\n  ▶ {i['title'][:40]}")
        try:
            print(f"    → {collect_one(i['url'], year, i['title'])}")
        except Exception as e:
            print(f"    → エラー: {e}")
        time.sleep(0.5)


# ------------------------------------------------------------ 画面（メニュー）
def ask_theme_year():
    themes = sorted({t for i in read_past_list() for t in i["themes"]})
    if not themes:
        return None, None
    print("\n  テーマを選んでください")
    for n, t in enumerate(themes, 1):
        print(f"   {n}) {THEME_NAMES.get(t, t)}")
    s = input("  番号 > ").strip()
    if not s.isdigit() or not 1 <= int(s) <= len(themes):
        return None, None
    theme = themes[int(s) - 1]
    years = sorted({i["year"] for i in read_past_list() if theme in i["themes"]}, reverse=True)
    y = input(f"  年を入力してください（あり: {', '.join(map(str, years))}） > ").strip()
    return (theme, int(y)) if y.isdigit() else (None, None)


def menu_list_saved():
    y = input("\n  年を入力（空欄ですべて） > ").strip()
    metas = archived_meta(int(y) if y.isdigit() else None)
    themes = {}
    for i in read_past_list():
        themes[(i["year"], i["slug"])] = i["themes"]
    print(f"\n  保存済み {len(metas)}件")
    for m in metas:
        th = ",".join(THEME_NAMES.get(t, t) for t in themes.get((m.get("year"), m.get("slug")), []))
        print(f"   {m.get('year')}  {m.get('slug', '')[:28]:<28} {th:<10} {m.get('title', '')[:30]}")


def menu_collect_url():
    url = input("\n  ツアーページのURL > ").strip()
    y = input("  開催した年 > ").strip()
    if not (url and y.isdigit()):
        return
    print(f"  → {collect_one(url, int(y))}")


def menu_build_model():
    cfgs = sorted(os.path.basename(p) for p in glob.glob(os.path.join(BASE_DIR, "*_config.json")))
    if not cfgs:
        print("  設定ファイル（○○_config.json）がありません。")
        return
    print("\n  作るページを選んでください")
    for n, c in enumerate(cfgs, 1):
        print(f"   {n}) {c}")
    s = input("  番号 > ").strip()
    if s.isdigit() and 1 <= int(s) <= len(cfgs):
        import build_momiji
        build_momiji.main(config_name=cfgs[int(s) - 1])


def main():
    while True:
        print("\n" + "=" * 50)
        print("  旅とも手帳　過去ツアー編集")
        print("=" * 50)
        print("  1) テーマと年を選んで、過去ツアーを保存版に取り込む")
        print("  2) URLを指定して、1件だけ取り込む")
        print("  3) 保存済みのツアーを確認する")
        print("  4) 季節ページを作る（モデルページの確認）")
        print("  0) 終了")
        s = input("  番号 > ").strip()
        if s == "1":
            theme, year = ask_theme_year()
            if theme:
                collect_by_theme(theme, year)
        elif s == "2":
            menu_collect_url()
        elif s == "3":
            menu_list_saved()
        elif s == "4":
            menu_build_model()
        elif s == "0":
            print("\n  取り込んだ内容は、次に run.py（HP更新）を実行したときにGitHubへ送られます。")
            return 0


if __name__ == "__main__":
    sys.exit(main())
