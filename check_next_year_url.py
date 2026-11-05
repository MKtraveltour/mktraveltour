"""
check_next_year_url.py
【募集終了】になったツアー（または自動で非表示になったツアー）について、
URLの年号を翌年に置き換えたページを探し、本当に翌年版が公開されていれば
scraper.py の TOUR_URLS を新しいURLに書き換えて再掲載する。

安全対策:
- ツール（tour_editor.py）で手動非表示にしたツアー（manual_hidden）は対象外
- 翌年URLがすでに別のツアーとして登録済みなら何もしない（二重掲載防止）
- ページが存在しても「ツアー詳細ページでない」「募集終了のまま」なら無効扱い
"""
import json
import os
import re
from datetime import date

try:
    import requests
    from bs4 import BeautifulSoup
    LIBS_OK = True
except ImportError:
    LIBS_OK = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOUR_DATA_PATH = os.path.join(BASE_DIR, "tour_data.json")
SCRAPER_PATH = os.path.join(BASE_DIR, "scraper.py")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

ENDED_WORDS = ("募集終了", "受付終了")


def load_tour_urls(src: str) -> dict:
    """scraper.py の TOUR_URLS を {key: url} として読み取る"""
    m = re.search(r"TOUR_URLS\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
    if not m:
        return {}
    return dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1)))


def normalize(url: str) -> str:
    """比較用にURLを正規化（?以降と末尾の/を無視）"""
    return url.split("?")[0].rstrip("/")


def make_next_year_candidates(url: str) -> list:
    """URLの年号を今年・来年に置き換えた候補（元より新しい年のみ）"""
    this_year = date.today().year
    candidates = []
    for yr in set(re.findall(r"20\d{2}", url)):
        for next_yr in (this_year, this_year + 1):
            if next_yr > int(yr):
                new_url = url.replace(yr, str(next_yr))
                if new_url not in candidates:
                    candidates.append(new_url)
    return candidates


def is_valid_tour_page(url: str, timeout: int = 10) -> bool:
    """実際にツアー詳細ページが公開されていて、募集中かどうかを確認"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return False
        # トップページ等へ転送された場合は無効
        if normalize(r.url) != normalize(url):
            return False
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("h1.c-tour-detail__heading-lv1")
        if h1 is None:
            return False  # ツアー詳細ページではない
        title = h1.get_text(strip=True)
        if any(w in title for w in ENDED_WORDS):
            return False  # 翌年版もまだ募集終了表示
        return True
    except Exception:
        return False


def check_and_update():
    if not LIBS_OK:
        print("  requests / beautifulsoup4 が未インストールのためスキップ")
        return
    if not (os.path.exists(TOUR_DATA_PATH) and os.path.exists(SCRAPER_PATH)):
        print("  tour_data.json または scraper.py が見つかりません")
        return

    with open(TOUR_DATA_PATH, "r", encoding="utf-8") as f:
        tours = json.load(f)
    with open(SCRAPER_PATH, "r", encoding="utf-8", newline="") as f:
        scraper_src = f.read()

    tour_urls = load_tour_urls(scraper_src)
    registered = {normalize(u) for u in tour_urls.values()}

    json_updated = False
    scraper_updated = False

    for key, old_url in tour_urls.items():
        tour = tours.get(key, {})
        if tour.get("manual_hidden"):
            continue  # 手動非表示はユーザーの判断を優先して触らない

        title = tour.get("title", "")
        is_ended = any(w in title for w in ENDED_WORDS) or tour.get("hidden", False)
        if not is_ended:
            continue  # 掲載中のツアーは対象外

        candidates = make_next_year_candidates(old_url)
        if not candidates:
            continue

        for new_url in candidates:
            if normalize(new_url) in registered:
                # 翌年版はすでに別のツアーとして登録済み → 二重掲載しない
                continue
            print(f"  🔍 {key}: {new_url} ", end="", flush=True)
            if not is_valid_tour_page(new_url):
                print("❌ 未公開")
                continue

            print("✅ 翌年版を発見！URLを更新します")
            # scraper.py の TOUR_URLS を書き換え（scraper.pyはここのURLを読みに行く）
            pattern = r'("' + re.escape(key) + r'"\s*:\s*")' + re.escape(old_url) + r'(")'
            scraper_src, n = re.subn(pattern, lambda m: m.group(1) + new_url + m.group(2), scraper_src)
            if n:
                scraper_updated = True
                registered.add(normalize(new_url))
            if key in tours:
                tours[key]["url"] = new_url
                tours[key]["hidden"] = False
                tours[key]["updated_at"] = str(date.today())
                json_updated = True
            break

    if scraper_updated:
        with open(SCRAPER_PATH, "w", encoding="utf-8", newline="") as f:
            f.write(scraper_src)
        print("  💾 scraper.py のURLを更新しました")
    if json_updated:
        with open(TOUR_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(tours, f, ensure_ascii=False, indent=2)
        print("  💾 tour_data.json を更新しました")
    if not (scraper_updated or json_updated):
        print("  変更なし")


if __name__ == "__main__":
    check_and_update()
