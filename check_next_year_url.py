"""
check_next_year_url.py
hidden:Trueのツアーに対して年号を翌年に置き換えたURLをチェックし、
有効なら自動的にURLを更新してhidden:Falseに変更する
"""
import json
import re
import os

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOUR_DATA_PATH = os.path.join(BASE_DIR, "tour_data.json")

def make_next_year_candidates(url: str) -> list:
    """URLの年号部分を翌年・翌々年に置き換えた候補リストを返す"""
    from datetime import date
    current_year = date.today().year
    candidates = []
    # 4桁年号をすべて置換候補として生成（2024→2025, 2025→2026など）
    years_in_url = re.findall(r'20\d{2}', url)
    for yr in set(years_in_url):
        yr_int = int(yr)
        # 現在年以降の年号に置き換え
        for next_yr in [current_year, current_year + 1]:
            if next_yr != yr_int:
                new_url = url.replace(yr, str(next_yr))
                if new_url != url and new_url not in candidates:
                    candidates.append(new_url)
    return candidates

def is_url_valid(url: str, timeout: int = 8) -> bool:
    """URLが有効（200 or 301/302）かチェック"""
    if not REQUESTS_OK:
        return False
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False

def check_and_update():
    if not os.path.exists(TOUR_DATA_PATH):
        print("  tour_data.json が見つかりません")
        return

    if not REQUESTS_OK:
        print("  requestsライブラリが未インストールのためスキップ")
        return

    with open(TOUR_DATA_PATH, "r", encoding="utf-8") as f:
        tours = json.load(f)

    updated = False
    for key, tour in tours.items():
        if not tour.get("hidden", False):
            continue  # 表示中はスキップ
        if tour.get("error"):
            continue

        old_url = tour.get("url", "")
        if not old_url:
            continue

        candidates = make_next_year_candidates(old_url)
        if not candidates:
            continue

        print(f"  🔍 {key}: 翌年URL候補をチェック中...")
        for new_url in candidates:
            print(f"      → {new_url} ", end="", flush=True)
            if is_url_valid(new_url):
                print("✅ 有効！")
                tour["url"]    = new_url
                tour["hidden"] = False
                # データをリセットして再取得させる
                tour["title"]      = "（次回run.py実行時に自動取得）"
                tour["dates"]      = []
                tour["statuses"]   = []
                tour["image"]      = ""
                tour["price"]      = ""
                tour["error"]      = False
                tour["updated_at"] = str(__import__('datetime').date.today())
                updated = True
                break
            else:
                print("❌ 無効")

    if updated:
        with open(TOUR_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(tours, f, ensure_ascii=False, indent=2)
        print("  💾 tour_data.json を更新しました")
    else:
        print("  変更なし")

if __name__ == "__main__":
    check_and_update()
