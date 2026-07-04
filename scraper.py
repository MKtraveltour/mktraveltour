"""
scraper.py
MKトラベル公式サイトから各ツアーの最新情報を取得してtour_data.jsonに保存する
"""

import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ===== 監視するツアーURLの一覧 =====
# 新しいツアーを追加する場合はここにURLと識別キーを追加するだけでOK
TOUR_URLS = {
    "ajisai_harf":    "https://travel.mk-group.co.jp/tourkyoto/2026ajisai-harf/",
    "ayabe_ajisai":   "https://travel.mk-group.co.jp/tourkyoto/ayabe-ajisai2026/",
    "rousoku":        "https://travel.mk-group.co.jp/tourkyoto/rousokumatsuri2026/",
    "himatsuri_stay": "https://travel.mk-group.co.jp/tourkyoto/himatsuri-stay/",
    "okuribi":        "https://travel.mk-group.co.jp/tourkyoto/okuribi2026/",
    "kokoro_utsushi": "https://travel.mk-group.co.jp/tourkyoto/yokokuji-limited/",
    "satsuei": "https://travel.mk-group.co.jp/tourkyoto/photo_yokokuji/",
    "momidiya": "https://travel.mk-group.co.jp/tourkyoto/momijiya-takao2026/",
    "himatsuri_1day": "https://travel.mk-group.co.jp/tourkyoto/himatsuri-1day/",
    "furin_shojuin2026": "https://travel.mk-group.co.jp/tourkyoto/furin-shojuin2026/",
    "migidaimonji2026": "https://travel.mk-group.co.jp/tourkyoto/migidaimonji2026/",
    "himatsuri2026":    "https://travel.mk-group.co.jp/tourkyoto/kuramanohimatsuri2026/",
    "miyama_ishida":    "https://travel.mk-group.co.jp/tourkyoto/miyama-ishida/",
    "yuzengiku2026":    "https://travel.mk-group.co.jp/tourkyoto/yuzengiku2026/",
    "yokokuji_shuttle": "https://travel.mk-group.co.jp/tourkyoto/yokokuji_shuttletour/",
    "shojuin_sogei":    "https://travel.mk-group.co.jp/tourkyoto/2021shojuin_sogei/",
    "uma":              "https://travel.mk-group.co.jp/tourkyoto/eto-uma/",
    "narihira_nishiyama": "https://travel.mk-group.co.jp/tourkyoto/narihira-nishiyama/",
    "tango":              "https://travel.mk-group.co.jp/tourkyoto/tango-private/",
    "baikamo2026": "https://travel.mk-group.co.jp/tourkyoto/baikamo2026/",

    "maizuru_ajisai": "https://travel.mk-group.co.jp/tourkyoto/2026maizuruajisai/",

    "yawata": "https://travel.mk-group.co.jp/tourkyoto/yawata/",

    "shasou": "https://travel.mk-group.co.jp/tourkyoto/kyoto-car2026/",

    "kayabuki_himawari": "https://travel.mk-group.co.jp/tourkyoto/kayabuki-himawari/",
    "eigamura-jidaigeki": "https://travel.mk-group.co.jp/tourkyoto/eigamura-jidaigeki/",

    "sagano_train": "https://travel.mk-group.co.jp/tourkyoto/sagano-train/",

}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_page(url: str) -> BeautifulSoup | None:
    """URLからHTMLを取得してBeautifulSoupオブジェクトを返す"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ERROR] {url} の取得失敗: {e}")
        return None


def extract_title(soup: BeautifulSoup) -> str:
    """ツアータイトルを取得"""
    h1 = soup.select_one("h1.c-tour-detail__heading-lv1")
    if h1:
        # leadテキスト（「京都観光タクシーツアー」）を除いたタイトルだけを取得
        lead = h1.select_one(".p-tour-detail__lead")
        if lead:
            lead.decompose()
        return h1.get_text(strip=True)
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True).split("｜")[0] if title_tag else "タイトル不明"


def extract_image(soup: BeautifulSoup) -> str:
    """メイン画像URLを取得"""
    # OGP画像が最も確実
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        return og_img["content"]
    # スライダー内の画像
    mv_img = soup.select_one(".p-tour-detail__mv-item img")
    if mv_img and mv_img.get("src"):
        return mv_img["src"]
    return ""


def extract_price(soup: BeautifulSoup) -> str:
    """料金を取得"""
    price_el = soup.select_one(".p-tour-detail__price-description")
    if price_el:
        text = price_el.get_text(strip=True)
        # 「円」が含まれていれば整形して返す
        if "円" in text:
            return text.replace("\xa0", "").strip()
    return ""


def extract_dates(soup: BeautifulSoup) -> list[str]:
    """出発予定日リストを取得"""
    dates = []
    date_section = soup.select_one(".p-tour-detail__departure-date")
    if date_section:
        spans = date_section.find_all("span")
        if spans:
            dates = [s.get_text(strip=True).replace("、", "") for s in spans]
        else:
            raw = date_section.get_text(strip=True)
            dates = [d.strip() for d in re.split(r"[、,，]", raw) if d.strip()]
    # caution文（補足テキスト）も取得
    caution = soup.select_one(".p-tour-detail__departure-caution")
    if caution:
        dates_text = caution.get_text(strip=True)
        if dates_text and dates_text not in dates:
            dates.append(dates_text)
    return dates


def _parse_status_line(line: str):
    """
    「7/2　　催行確定」「7/5　　催行まであと２名」のような1行分のテキストから
    日付・ラベル・タイプを抽出する。該当しなければNoneを返す。
    """
    line = line.strip()
    if not line:
        return None

    date_match = re.search(r"\d+/\d+", line)
    if not date_match:
        return None
    date = date_match.group()

    if "催行確定" in line:
        return {"date": date, "label": "催行確定", "type": "confirmed"}
    if "満席" in line:
        return {"date": date, "label": "満席", "type": "full"}
    if "催行まであと" in line or "あと" in line:
        m = re.search(r"あと(\d+)名", line)
        remaining = m.group(1) if m else "?"
        return {"date": date, "label": f"あと{remaining}名", "type": "few"}
    return None


def extract_status(soup: BeautifulSoup) -> list[dict]:
    """
    催行状況テーブルから日付ごとのステータスを取得
    戻り値例: [{"date": "6/20", "label": "催行確定", "type": "confirmed"}, ...]

    1つの<td>に複数日程が<br>区切りで詰め込まれているケース
    （例：「7/2 催行確定<br>7/3 催行まであと３名<br>8/14 催行まであと２名」）に対応するため、
    <td>のテキストをまとめて取得するのではなく、<br>ごとに1行ずつ分割してから
    日付・ステータスを判定する。これにより、1日だけ催行確定でも
    同じセル内の他の日程まで巻き込んで「催行確定」になってしまう不具合を防ぐ。
    """
    statuses = []
    seen_dates = set()

    def add_status(item):
        if item and item["date"] not in seen_dates:
            seen_dates.add(item["date"])
            statuses.append(item)

    content_section = soup.select_one(".p-tour-detail__content-section")
    if content_section:
        for td in content_section.find_all("td"):
            # <br>タグを改行に置換してから1行ずつ判定する
            html_str = td.decode_contents()
            html_str = re.sub(r"<br\s*/?>", "\n", html_str, flags=re.IGNORECASE)
            line_soup = BeautifulSoup(html_str, "html.parser")
            full_text = line_soup.get_text()
            for line in full_text.split("\n"):
                add_status(_parse_status_line(line))

    # 日付なしの「満席」「催行確定」表示に対応
    # 出発予定日が1日のみの場合は常に補完を試みる
    if not statuses:
        red_texts = soup.select(".p-tour-detail__text-red")
        date_section = soup.select_one('.p-tour-detail__departure-date')
        single_date = None
        if date_section:
            spans = date_section.find_all('span')
            valid_dates = []
            for span in spans:
                d_text = span.get_text(strip=True).replace('、', '')
                m = re.search(r'(\d+)/(\d+)', d_text)
                if m and '～' not in d_text:
                    valid_dates.append(m.group(1) + '/' + m.group(2))
            if len(valid_dates) == 1:
                single_date = valid_dates[0]

        for el in red_texts:
            text = el.get_text(strip=True)
            is_full = '満席' in text and not re.search(r'\d+/\d+', text)
            is_confirmed = '催行確定' in text and not re.search(r'\d+/\d+', text)
            if is_full or is_confirmed:
                target_date = single_date
                if not target_date and date_section:
                    spans = date_section.find_all('span')
                    for span in spans:
                        d_text = span.get_text(strip=True).replace('、', '')
                        m = re.search(r'(\d+)/(\d+)', d_text)
                        if m:
                            target_date = m.group(1) + '/' + m.group(2)
                            break
                if target_date:
                    if is_full:
                        statuses.append({'date': target_date, 'label': '満席', 'type': 'full'})
                    else:
                        statuses.append({'date': target_date, 'label': '催行確定', 'type': 'confirmed'})
                break
        # 出発予定日が1日のみで赤字テキストに催行確定がある場合も補完
        if not statuses and single_date:
            for el in red_texts:
                text = el.get_text(strip=True)
                if '催行確定' in text:
                    statuses.append({'date': single_date, 'label': '催行確定', 'type': 'confirmed'})
                    break
                elif '満席' in text:
                    statuses.append({'date': single_date, 'label': '満席', 'type': 'full'})
                    break
    return statuses


def extract_category_tags(soup: BeautifulSoup) -> list[str]:
    """タグ（カテゴリ）を取得"""
    tags = []
    tag_links = soup.select(".p-tag__wrap .p-tag")
    for tag in tag_links:
        tags.append(tag.get_text(strip=True))
    return tags


def scrape_tour(key: str, url: str) -> dict:
    """1ツアーページをスクレイピングしてデータを返す"""
    print(f"  取得中: {key} ({url})")
    soup = fetch_page(url)
    if soup is None:
        return {"key": key, "url": url, "error": "取得失敗", "updated_at": datetime.now().isoformat()}

    data = {
        "key":       key,
        "url":       url,
        "title":     extract_title(soup),
        "image":     extract_image(soup),
        "price":     extract_price(soup),
        "dates":     extract_dates(soup),
        "statuses":  extract_status(soup),
        "tags":      extract_category_tags(soup),
        "updated_at": datetime.now().isoformat(),
        "error":     None,
    }
    print(f"    タイトル: {data['title']}")
    print(f"    料金:     {data['price']}")
    print(f"    出発日:   {data['dates'][:3]}...")
    print(f"    催行状況: {data['statuses'][:3]}")
    return data


def main():
    print(f"=== スクレイピング開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    results = {}
    success = 0
    fail    = 0

    for key, url in TOUR_URLS.items():
        try:
            data = scrape_tour(key, url)
            results[key] = data
            if data.get("error"):
                fail += 1
            else:
                success += 1
        except Exception:
            print(f"  [ERROR] {key} で予期せぬエラー:")
            traceback.print_exc()
            results[key] = {"key": key, "url": url, "error": "例外発生", "updated_at": datetime.now().isoformat()}
            fail += 1

    # JSONに保存
    out_path = Path(__file__).parent / "tour_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完了: 成功{success}件 / 失敗{fail}件 ===")
    print(f"保存先: {out_path}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
