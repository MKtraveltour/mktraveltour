"""
generate_hp_auto.py
tour_data.json を読み込んで index.html を自動生成する
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ===== カレンダー用：日付文字列 → (year, month, day) に変換 =====
def parse_date(date_str: str, default_year: int = 2026):
    """
    '6/21(日)' や '10/22(木)' → (2026, 6, 21) のように変換
    失敗した場合は None を返す
    """
    # 「随時催行」「※」などの特殊文字列はスキップ
    if not date_str or "随時" in date_str or date_str.startswith("※"):
        return None
    m = re.search(r"(\d+)/(\d+)", date_str)
    if m:
        month = int(m.group(1))
        day   = int(m.group(2))
        # 月・日の範囲チェック
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (default_year, month, day)
    return None


# ===== ツアーレポート辞書 =====
# カレンダーの日付とレポートページ・写真を紐付け
# 新しいツアーを追加するときはここに追記するだけ
TOUR_REPORTS = {
    "2025-10-22": {
        "title": "鞍馬の火祭×くらま温泉 癒し旅",
        "page": "himatsuri2025.html",
        "photos": [
            "https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/21f355c5596cd370e7f58f9c99c3b246-600x400.webp",
            "https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/f9b7e4277e1c0a018981566ed4e8087e-600x400.webp",
            "https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/4a3e24e959e0275abd2df3e85320065c-600x400.webp",
        ]
    },
}

# ツアーキーワード→絵文字マッピング
TOUR_EMOJI = {
    '風鈴':     '🔔',
    'ろうそく': '🕯',
    '送り火':   '🔥',
    '火祭':     '🔥',
    'あじさい': '🌸',
    '紫陽花':   '🌸',
    'こころうつし': '🍃',
    '撮影':     '📷',
    '川床':     '🍽',
    '御所':     '🌙',
    '右大文字': '🌙',
    '鞍馬':     '🔥',
    '馬':       '🐎',
    '写経':     '🍵',
    '茶の湯':   '🍵',
    '岡林院':   '🍵',
    'ねねと秀吉': '📜',
    '豊国神社': '📜',
    '高台寺':   '📜',
}

def get_tour_emoji(title: str) -> str:
    for keyword, emoji in TOUR_EMOJI.items():
        if keyword in title:
            return emoji
    return '📅'

def build_tour_js(tours: dict) -> str:
    """tour_data.json からカレンダー用JSデータを生成"""
    lines = []
    for key, tour in tours.items():
        if tour.get("error"):
            continue
        url = tour["url"]
        title = tour["title"].replace("'", "\\'")

        # 催行確定・満席・few の日付を収集
        status_map = {}
        for s in tour.get("statuses", []):
            date_str = s["date"]
            parsed = parse_date(date_str)
            if parsed:
                y, mo, d = parsed
                k = f"{y}-{mo}-{d}"
                # confirmed > full > few > tour の優先順位
                existing = status_map.get(k, {}).get("type", "")
                new_type = s["type"]
                priority = {"confirmed": 3, "full": 2, "few": 1, "tour": 0}
                if priority.get(new_type, 0) >= priority.get(existing, 0):
                    status_map[k] = {"type": new_type, "label": s["label"]}

        # 出発日すべてを「ツアーあり」として登録（まだ登録されていない日付のみ）
        for date_str in tour.get("dates", []):
            parsed = parse_date(date_str)
            if parsed:
                y, mo, d = parsed
                k = f"{y}-{mo}-{d}"
                if k not in status_map:
                    status_map[k] = {"type": "tour", "label": ""}

        # JS コードに変換
        var_url = f"_u_{key.replace('-', '_')}"
        lines.append(f"      var {var_url} = '{url}';")
        for k, info in status_map.items():
            t = info["type"]
            label = info["label"].replace("'", "\\'")
            note = f"{title} {label}".strip()
            emoji = get_tour_emoji(title)
            # 既存エントリに絵文字を追加（同じ日付に複数ツアーがある場合）
            existing_idx = None
            for i, line in enumerate(lines):
                if f"TOUR['{k}']" in line:
                    existing_idx = i
                    break
            if existing_idx is not None:
                import re as _re
                m2 = _re.search(r"em:'([^']*)'", lines[existing_idx])
                if m2:
                    existing_em = m2.group(1)
                    if emoji and emoji not in existing_em:
                        lines[existing_idx] = lines[existing_idx].replace(
                            f"em:'{existing_em}'", f"em:'{existing_em}{emoji}'"
                        )
            else:
                lines.append(
                    f"      TOUR['{k}'] = {{st:'{t}', ti:'{title}', ur:{var_url}, nt:'{note}', em:'{emoji}'}};"
                )

    return "\n".join(lines)


def build_tour_cards(tours: dict) -> str:
    """tour_data.json からツアーカードHTMLを生成"""

    # カテゴリタグ判定
    def get_tag_class(tags: list) -> tuple:
        """タグリストからCSSクラスとラベルを返す（最大2つ）"""
        mapping = {
            "イベント": ("tev", "イベント・お祭り"),
            "お祭り":   ("tev", "イベント・お祭り"),
            "歴史":     ("th",  "歴史・社寺巡り"),
            "社寺":     ("th",  "歴史・社寺巡り"),
            "体験":     ("te",  "体験・名所巡り"),
            "名所":     ("te",  "体験・名所巡り"),
            "季節":     ("th",  "季節の花"),
            "花":       ("th",  "季節の花"),
        }
        result = []
        used = set()
        for tag in tags:
            for keyword, (cls, label) in mapping.items():
                if keyword in tag and label not in used:
                    result.append((cls, label))
                    used.add(label)
                    break
            if len(result) >= 2:
                break
        if not result:
            result = [("te", "体験・名所巡り")]
        return result

    # 催行状況バッジ判定
    def get_badge(statuses: list) -> tuple:
        """最も重要なステータスのバッジを返す (class, text)"""
        if not statuses:
            return ("br", "募集中")
        types = [s["type"] for s in statuses]
        if "confirmed" in types:
            return ("bc", "催行確定日あり")
        if "full" in types:
            return ("bfull", "満席")
        if "few" in types:
            # あと何席か
            for s in statuses:
                if s["type"] == "few":
                    return ("bfw", s["label"])
        return ("br", "募集中")

    # 日付表示文字列
    def format_dates(dates: list) -> str:
        if not dates:
            return "—"
        # caution行（期間表示）があればそちらを優先
        for d in dates:
            if "〜" in d or "~" in d or ("/" in d and "(" not in d):
                return d
        # 最初の3件を表示
        shown = [d for d in dates if re.search(r"\d+/\d+", d)][:3]
        text = "・".join(shown)
        if len(dates) > 3:
            text += " 他"
        return text or dates[0]

    bg_colors = ["#6b8e6b", "#7c6b4a", "#4a7c6b", "#3a2a1a"]
    cards_html = []
    for i, (key, tour) in enumerate(tours.items()):
        if tour.get("error"):
            # エラーの場合は準備中カード
            cards_html.append(f"""      <div class="tour-card" style="opacity:0.55;">
        <div class="tour-img" style="background:#b0a090;">
          <div style="padding:10px;text-align:center;">取得エラー<br><small>{tour['url']}</small></div>
          <div class="sbadge br">取得失敗</div>
        </div>
        <div class="tour-body">
          <div class="tour-title">データ取得に失敗しました</div>
          <div class="tour-date">—</div>
          <span class="btn-detail" style="background:#b0a090;cursor:default;">エラー</span>
        </div>
      </div>""")
            continue

        title    = tour["title"]
        url      = tour["url"]
        image    = tour.get("image", "")
        price    = tour.get("price", "")
        tags     = tour.get("tags", [])
        statuses = tour.get("statuses", [])
        dates    = tour.get("dates", [])

        tag_items = get_tag_class(tags)
        badge_cls, badge_text = get_badge(statuses)
        date_text = format_dates(dates)
        bg_color = bg_colors[i % len(bg_colors)]

        tag_html = "".join(
            f'<span class="ttag {cls}">{label}</span>'
            for cls, label in tag_items
        )

        img_html = ""
        if image:
            img_html = (
                f'<img src="{image}" alt="{title}" '
                f'style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;object-position:50% 30%;" '
                f'onerror="this.style.display=\'none\'">'
            )

        # タグからフィルター用data属性を生成
        filter_tags = []
        for t in tags:
            if 'イベント' in t or 'お祭り' in t: filter_tags.append('event')
            if '体験' in t or '名所' in t:       filter_tags.append('exp')
            if '歴史' in t or '社寺' in t:       filter_tags.append('history')
            if '季節' in t or '花' in t:         filter_tags.append('flower')
            if '夏' in t:                        filter_tags.append('summer')
            if '秋' in t:                        filter_tags.append('autumn')
            if '春' in t:                        filter_tags.append('spring')
            if '冬' in t:                        filter_tags.append('winter')
        data_tags = ' '.join(set(filter_tags)) or 'other'

        # レポートバッジ生成（月日だけで照合）
        report_badge = ""
        for report_key, report_val in TOUR_REPORTS.items():
            # report_keyは "2025-10-22" 形式 → 月日だけ取り出す
            rk_parts = report_key.split("-")
            if len(rk_parts) == 3:
                rk_md = f"{int(rk_parts[1])}/{int(rk_parts[2])}"
                # ツアーのdatesと照合
                for date_str in dates:
                    m = __import__('re').search(r'(\d+)/(\d+)', date_str)
                    if m and f"{int(m.group(1))}/{int(m.group(2))}" == rk_md:
                        report_badge = f' <a href="{report_val["page"]}" style="font-size:13px;text-decoration:none;vertical-align:middle;" title="当日のレポートを見る">📄</a>'
                        break
            if report_badge:
                break

        # data-dates生成（カレンダーキーと同じ形式 "2026-M-D"）
        card_date_keys = []
        for date_str in dates:
            parsed = parse_date(date_str)
            if parsed:
                y, mo, d = parsed
                card_date_keys.append(f"{y}-{mo}-{d}")
        for s in statuses:
            parsed = parse_date(s['date'])
            if parsed:
                y, mo, d = parsed
                k = f"{y}-{mo}-{d}"
                if k not in card_date_keys:
                    card_date_keys.append(k)
        data_dates_attr = ','.join(card_date_keys)

        cards_html.append(f"""      <div class="tour-card" data-tags="{data_tags}" data-dates="{data_dates_attr}">
        <div class="tour-img" style="background:{bg_color};position:relative;overflow:hidden;">
          {img_html}
          <div class="sbadge {badge_cls}" style="z-index:1;">{badge_text}</div>
        </div>
        <div class="tour-body">
          <div class="tour-tags">{tag_html}</div>
          <div class="tour-title">{title}{report_badge}</div>
          <div class="tour-date">{date_text}</div>
          <div class="tour-price">大人1名 {price}</div>
          <a href="{url}" target="_blank" class="btn-detail">詳細をみる</a>
        </div>
      </div>""")

    return "\n".join(cards_html)


def build_sidebar_status(tours: dict) -> str:
    """右サイドバーの催行状況リストを生成"""
    items = []
    for key, tour in tours.items():
        if tour.get("error"):
            continue
        title_short = tour["title"][:12] + ("…" if len(tour["title"]) > 12 else "")
        statuses = tour.get("statuses", [])

        if not statuses:
            items.append(
                f'      <div class="status-item">'
                f'<span class="sname">{title_short}</span>'
                f'<span class="stag" style="background:#2980b9;color:#fff">募集中</span>'
                f'</div>'
            )
            continue

        # 催行確定があれば優先表示
        confirmed = [s for s in statuses if s["type"] == "confirmed"]
        if confirmed:
            s = confirmed[0]
            items.append(
                f'      <div class="status-item">'
                f'<span class="sname">{title_short} {s["date"]}</span>'
                f'<span class="stag" style="background:#27ae60;color:#fff">催行確定</span>'
                f'</div>'
            )
        else:
            # あと何席かを表示
            few = [s for s in statuses if s["type"] == "few"]
            full = [s for s in statuses if s["type"] == "full"]
            if full:
                s = full[0]
                items.append(
                    f'      <div class="status-item full-s">'
                    f'<span class="sname">{title_short} {s["date"]}</span>'
                    f'<span class="stag" style="background:#c0392b;color:#fff">満席</span>'
                    f'</div>'
                )
            elif few:
                s = few[0]
                items.append(
                    f'      <div class="status-item">'
                    f'<span class="sname">{title_short} {s["date"]}</span>'
                    f'<span class="stag" style="background:#e67e22;color:#fff">{s["label"]}</span>'
                    f'</div>'
                )

    return "\n".join(items[:5])


# ===== HTML テンプレート =====
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MKトラベル手帳 | MKトラベル</title>
  <!-- 公開時にこの1行を削除してください -->
  <meta name="robots" content="noindex,nofollow">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Noto Sans JP', sans-serif; font-size: 14px; color: #3c2e1e; background: #f5f0e8; }}
    a {{ text-decoration: none; color: inherit; }}
    .nav {{ background: #8b7355; display: flex; width: 100%; position: sticky; top: 0; z-index: 100; }}
    .nav a {{ color: #fff; text-align: center; padding: 14px 0; flex: 1; font-size: 13px; font-weight: 500; border-right: 1px solid rgba(255,255,255,0.2); transition: background 0.2s; }}
    .nav a:last-child {{ border-right: none; }}
    .nav a span {{ display: block; font-size: 11px; opacity: 0.7; margin-top: 2px; }}
    .nav a:hover {{ background: rgba(255,255,255,0.15); }}
    .hero {{ background: #8b7355; color: #fff; padding: 28px 24px; text-align: center; position: relative; }}
    .hero h1 {{ font-size: 22px; font-weight: 500; margin-bottom: 6px; color: #fff; }}
    .hero p  {{ font-size: 14px; color: #fff; opacity: 0.9; }}
    .page-wrap {{ display: grid; grid-template-columns: 160px 1fr 260px; max-width: 1200px; margin: 0 auto; background: #fff; }}
    .blog-nav {{ background: #faf8f5; border-right: 1px solid #e0d8cc; padding: 16px 0; min-height: 100vh; }}
    .blog-nav-title {{ font-size: 13px; font-weight: 500; color: #5c4a32; padding: 0 14px 10px; border-bottom: 3px solid #8b7355; margin-bottom: 4px; display: flex; align-items: center; gap: 5px; }}
    .bnav-category {{ border-bottom: 1px solid #ede8e0; }}
    .bnav-cat-label {{ display: flex; align-items: center; justify-content: space-between; padding: 9px 14px; font-size: 12px; color: #5c4a32; font-weight: 500; cursor: pointer; }}
    .bnav-cat-label:hover {{ background: #f0ebe2; }}
    .bnav-sub a {{ display: flex; align-items: center; justify-content: space-between; padding: 6px 14px 6px 22px; font-size: 11px; color: #7c6040; cursor: pointer; }}
    .bnav-sub a:hover {{ background: #f0ebe2; color: #5c4a32; }}
    .bnav-sub a.active {{ color: #8b7355; font-weight: 500; background: #f5ede0; }}
    .new-badge {{ background: #c0392b; color: #fff; font-size: 10px; padding: 1px 6px; border-radius: 10px; font-weight: 500; }}
    .blog-new-btn {{ margin: 14px 14px 0; background: #8b7355; color: #fff; border-radius: 6px; padding: 9px 10px; font-size: 12px; text-align: center; cursor: pointer; font-weight: 500; }}
    .blog-new-btn:hover {{ background: #7a6448; }}
    .content {{ padding: 18px; background: #fff; }}
    .breadcrumb {{ font-size: 12px; color: #999; margin-bottom: 14px; }}
    .breadcrumb span {{ color: #8b7355; }}
    .section-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }}
    .section-title {{ font-size: 14px; font-weight: 500; color: #5c4a32; border-left: 4px solid #8b7355; padding-left: 10px; }}
    .see-all {{ font-size: 12px; color: #8b7355; cursor: pointer; }}
    .see-all:hover {{ text-decoration: underline; }}
    .calendar-wrap {{ background: #fff; border: 1px solid #e0d8cc; border-radius: 10px; padding: 16px; margin-bottom: 20px; }}
    .cal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
    .cal-header h3 {{ font-size: 15px; font-weight: 500; color: #5c4a32; }}
    .cal-header button {{ background: none; border: 1px solid #c5b8a8; border-radius: 4px; padding: 4px 12px; cursor: pointer; color: #8b7355; font-size: 13px; }}
    .cal-header button:hover {{ background: #f5ede0; }}
    .cal-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }}
    .cdl {{ text-align: center; font-size: 12px; color: #999; padding: 5px 0; font-weight: 500; }}
    .cdl.sun {{ color: #c0392b; }} .cdl.sat {{ color: #2980b9; }}
    .cd {{ text-align: center; font-size: 13px; padding: 8px 2px; border-radius: 5px; cursor: pointer; }}
    .cd.has-tour  {{ background: #f0e8d8; color: #5c4a32; font-weight: 500; }}
    .cd.confirmed {{ background: #8b7355; color: #fff; font-weight: 500; }}
    .cd.full      {{ background: #c0392b; color: #fff; font-weight: 500; }}
    .cd.today     {{ outline: 3px solid #fff; outline-offset: -3px; box-shadow: 0 0 0 3px #8b7355; }}
    .cal-legend {{ display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap; }}
    .cl-item {{ display: flex; align-items: center; gap: 5px; font-size: 12px; color: #888; }}
    .cl-dot  {{ width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0; }}
    .filter-tabs {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }}
    .ftab {{ padding: 6px 14px; border-radius: 20px; font-size: 12px; cursor: pointer; border: 1px solid #8b7355; color: #8b7355; background: #fff; transition: all 0.15s; }}
    .ftab.active {{ background: #8b7355; color: #fff; }}
    .ftab:hover {{ background: #f5ede0; }}
    .tour-count {{ font-size: 12px; color: #999; margin-bottom: 10px; }}
    .tours-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }}
    .tour-card.hidden {{ display: none; }}
    .cd.selected {{ outline: 3px solid #5c4a32; outline-offset: -2px; }}
    .filter-note {{ font-size: 12px; color: var(--color-text-secondary, #888); background: #f5f0e8; border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; display: none; }}
    .filter-note.show {{ display: block; }}
    .reset-link {{ font-size: 12px; color: #8b7355; cursor: pointer; text-decoration: underline; display: none; }}
    .tour-card {{ background: #fff; border: 1px solid #d0c4b0; border-radius: 10px; overflow: hidden; transition: box-shadow 0.2s; }}
    .tour-card:hover {{ box-shadow: 0 2px 10px rgba(139,115,85,0.15); }}
    .tour-img {{ width: 100%; height: 180px; position: relative; overflow: hidden; font-size: 13px; color: #fff; font-weight: 500; background: #1a1a1a; }}
    .sbadge {{ position: absolute; top: 6px; right: 6px; font-size: 11px; padding: 2px 10px; border-radius: 4px; font-weight: 500; }}
    .bc {{ background: #27ae60; color: #fff; }} .bfw {{ background: #e67e22; color: #fff; }}
    .bfull {{ background: #c0392b; color: #fff; }} .br {{ background: #2980b9; color: #fff; }}
    .tour-body {{ padding: 12px; }}
    .tour-tags {{ display: flex; gap: 4px; margin-bottom: 6px; flex-wrap: wrap; }}
    .ttag {{ font-size: 10px; padding: 2px 7px; border-radius: 3px; border: 1px solid; }}
    .th  {{ color: #7c5c2e; border-color: #c5a87a; background: #fdf5e8; }}
    .te  {{ color: #4a7c4a; border-color: #7ab87a; background: #e8f5e8; }}
    .tev {{ color: #6b4a7c; border-color: #b87ab8; background: #f5e8f5; }}
    .tour-title {{ font-size: 13px; font-weight: 500; color: #3c2e1e; margin-bottom: 5px; line-height: 1.45; }}
    .tour-date  {{ font-size: 12px; color: #888; margin-bottom: 3px; }}
    .tour-price {{ font-size: 13px; color: #5c4a32; font-weight: 500; margin-bottom: 8px; }}
    .btn-detail {{ display: block; text-align: center; background: #8b7355; color: #fff; border-radius: 5px; padding: 7px; font-size: 12px; cursor: pointer; font-weight: 500; transition: background 0.2s; }}
    .btn-detail:hover {{ background: #7a6448; }}
    .news-post {{ background: #fff; border: 1px solid #e0d8cc; border-radius: 8px; padding: 12px; margin-bottom: 8px; }}
    .news-meta {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
    .nav-avatar {{ width: 30px; height: 30px; border-radius: 50%; background: #8b7355; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 12px; font-weight: 500; flex-shrink: 0; }}
    .news-author {{ font-size: 12px; font-weight: 500; color: #5c4a32; }}
    .news-dt {{ font-size: 11px; color: #999; }}
    .news-text {{ font-size: 12px; color: #3c2e1e; line-height: 1.6; }}
    .news-tag {{ color: #8b7355; font-size: 11px; margin-top: 4px; }}
    .photo-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 20px; }}
    .pt {{ border-radius: 6px; aspect-ratio: 1; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; font-weight: 500; cursor: pointer; }}
    .p1{{ background:#6b8e6b; }} .p2{{ background:#c5a87a; }} .p3{{ background:#7c9cc5; }}
    .p4{{ background:#c57a9c; }} .p5{{ background:#7cc57a; }}
    .p-upload {{ background: #f5f0e8; border: 2px dashed #c5b8a8; border-radius: 6px; aspect-ratio: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; gap: 4px; }}
    .p-upload:hover {{ background: #ede5d8; }}
    .p-upload i {{ font-size: 22px; color: #8b7355; }}
    .p-upload span {{ font-size: 11px; color: #8b7355; }}
    .sidebar {{ padding: 16px; border-left: 1px solid #e0d8cc; background: #faf8f5; }}
    .sb-block {{ background: #fff; border: 1px solid #e0d8cc; border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
    .sb-title {{ font-size: 13px; font-weight: 500; color: #5c4a32; border-bottom: 1px solid #e0d8cc; padding-bottom: 6px; margin-bottom: 10px; }}
    .status-item {{ display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; background: #faf8f5; border-radius: 4px; margin-bottom: 5px; border-left: 3px solid #8b7355; }}
    .status-item.full-s {{ border-left-color: #c0392b; }}
    .status-item.cancel-s {{ border-left-color: #95a5a6; }}
    .sname {{ color: #3c2e1e; font-weight: 500; flex: 1; margin-right: 6px; font-size: 11px; line-height: 1.3; }}
    .stag {{ font-size: 10px; padding: 2px 7px; border-radius: 3px; font-weight: 500; white-space: nowrap; }}
    .sns-btn {{ display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; border: 1px solid #e0d8cc; color: #3c2e1e; background: #fff; margin-bottom: 6px; width: 100%; transition: opacity 0.2s; }}
    .sns-btn:hover {{ opacity: 0.85; }}
    .sns-line {{ background: #06c755; color: #fff; border-color: #06c755; }}
    .sns-x {{ background: #000; color: #fff; border-color: #000; }}
    .sns-insta {{ background: #e1306c; color: #fff; border-color: #e1306c; }}
    .sns-youtube {{ background: #ff0000; color: #fff; border-color: #ff0000; }}
    .past-item {{ font-size: 13px; color: #8b7355; cursor: pointer; padding: 6px 0; border-bottom: 1px solid #f0e8d8; }}
    .past-item:last-child {{ border-bottom: none; }}
    .login-btn {{ background: #8b7355; color: #fff; text-align: center; padding: 8px; border-radius: 6px; font-size: 12px; cursor: pointer; margin-top: 8px; font-weight: 500; }}
    .login-btn:hover {{ background: #7a6448; }}
    .updated-note {{ font-size: 11px; color: #aaa; text-align: right; padding: 4px 18px; background: #fff; }}
    @media (max-width: 900px) {{
      .page-wrap {{ grid-template-columns: 1fr; }}
      .blog-nav {{ display: none; }}
      .sidebar {{ border-left: none; border-top: 1px solid #e0d8cc; }}
      .tours-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 600px) {{
      .tours-grid {{ grid-template-columns: 1fr; }}
      .nav a span {{ display: none; }}
    }}
  </style>
</head>
<body>



<div class="hero" id="hero-section">
  <div style="position:absolute;inset:0;overflow:hidden;">
    <img src="https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/hero-bg.png"
         alt="ヒーロー背景"
         style="width:100%;height:100%;object-fit:cover;opacity:0.3;">
  </div>
  <div style="position:relative;z-index:1;">
    <h1>MKトラベル手帳</h1>
    <p>ＭＫドライバーが案内する、ここだけの京都体験</p>
  </div>
</div>

<p class="updated-note">最終更新: {updated_at}</p>

<div class="page-wrap">

  <!-- 左：ブログナビ -->
  <aside class="blog-nav">
    <div class="blog-nav-title"><i class="ti ti-notebook"></i>ツアー日記</div>
    <div class="bnav-category">
      <div class="bnav-cat-label">造成日記 <i class="ti ti-chevron-down"></i></div>
      <div class="bnav-sub">
        <a href="#"><i class="ti ti-chevron-right"></i>すべて</a>
        <a href="#" class="active" style="gap:6px"><span style="display:flex;align-items:center;gap:4px"><i class="ti ti-chevron-right"></i>New！</span><span class="new-badge">3</span></a>
        <a href="#"><i class="ti ti-chevron-right"></i>企画のたまご</a>
        <a href="#"><i class="ti ti-chevron-right"></i>レポート</a>
        <a href="#"><i class="ti ti-chevron-right"></i>完成！</a>
      </div>
    </div>
    <div class="bnav-category">
      <div class="bnav-cat-label">季節・テーマ <i class="ti ti-chevron-down"></i></div>
      <div class="bnav-sub">
        <a href="#"><i class="ti ti-chevron-right"></i>春の京都</a>
        <a href="#"><i class="ti ti-chevron-right"></i>夏祭り</a>
        <a href="#"><i class="ti ti-chevron-right"></i>紅葉の秋</a>
        <a href="#"><i class="ti ti-chevron-right"></i>冬の情緒</a>
      </div>
    </div>
    <div class="bnav-category">
      <div class="bnav-cat-label">目的別 <i class="ti ti-chevron-down"></i></div>
      <div class="bnav-sub">
        <a href="#"><i class="ti ti-chevron-right"></i>イベント・お祭り</a>
        <a href="#"><i class="ti ti-chevron-right"></i>体験・名所巡り</a>
        <a href="#"><i class="ti ti-chevron-right"></i>歴史・社寺巡り</a>
      </div>
    </div>
    <div class="bnav-category" style="border-bottom:none">
    <div class="blog-new-btn"><i class="ti ti-edit"></i> 新規投稿</div>
  </aside>

  <!-- 中央：メインコンテンツ -->
  <main class="content">
    <p class="breadcrumb">ホーム &gt; <span>最新情報・募集中ツアー</span></p>

    <!-- カレンダー -->
    <div class="calendar-wrap">
      <div class="cal-header">
        <button onclick="calMove(-1)">&lt;</button>
        <h3>
          <i class="ti ti-calendar" style="font-size:15px;vertical-align:-2px;margin-right:5px;"></i>
          <span id="cal-month-label" style="font-size:15px;">読み込み中...</span>
        </h3>
        <button onclick="calMove(1)">&gt;</button>
      </div>
      <div id="cal-grid-area" style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px;"></div>
      <div class="cal-legend">
        <div class="cl-item"><div class="cl-dot" style="background:#f0e8d8;border:1px solid #c5b8a8;"></div>ツアーあり</div>
        <div class="cl-item"><div class="cl-dot" style="background:#8b7355;"></div>催行確定</div>
        <div class="cl-item"><div class="cl-dot" style="background:#c0392b;"></div>満席</div>
        <div class="cl-item"><div class="cl-dot" style="outline:2px solid #8b7355;outline-offset:-1px;"></div>本日</div>
      </div>
      <p style="font-size:11px;color:#999;margin-top:8px;">※色付き日付をクリックするとツアー詳細ページを開きます</p>
    </div>

    <!-- 募集中ツアー -->
    <div class="section-header">
      <div class="section-title">募集中のツアー</div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="reset-link" id="tour-reset" onclick="tourReset()">すべて表示 ×</span>
        <a href="https://travel.mk-group.co.jp/tourkyoto/" target="_blank" class="see-all">すべて見る →</a>
      </div>
    </div>
    <div class="filter-note" id="tour-filter-note"></div>
    <div class="filter-tabs">
      <div class="ftab active" onclick="tourFilter('all', this)">すべて</div>
      <div class="ftab" onclick="tourFilter('event', this)">イベント・お祭り</div>
      <div class="ftab" onclick="tourFilter('exp', this)">体験・名所巡り</div>
      <div class="ftab" onclick="tourFilter('history', this)">歴史・社寺巡り</div>
      <div class="ftab" onclick="tourFilter('flower', this)">季節の花</div>
      <div class="ftab" onclick="tourFilter('summer', this)">夏のツアー</div>
      <div class="ftab" onclick="tourFilter('autumn', this)">秋のツアー</div>
    </div>
    <div class="tour-count" id="tour-count"></div>
    <div class="tours-grid" id="tours-grid">
{tour_cards}
    </div>
    <!-- ツアーレポートセクション（カレンダー日付クリック時に表示） -->
    <div id="tour-report-section" style="display:none;margin-top:16px;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
        <div class="section-title">
          <i class="ti ti-camera" style="font-size:14px;vertical-align:-2px;margin-right:5px;"></i>
          当日の様子
        </div>
        <a id="tour-report-link" href="#" class="see-all">すべて見る →</a>
      </div>
      <div id="tour-report-photos" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:16px;"></div>
    </div>


    <!-- ツアー日記（Xリンクボタン方式） -->
    <div class="section-header" style="margin-top:16px;">
      <div class="section-title">
        <i class="ti ti-notebook" style="font-size:14px;vertical-align:-2px;margin-right:5px;"></i>
        ツアー日記 / 担当者からのお知らせ
      </div>
      <a href="https://x.com/mk_ryokou" target="_blank" class="see-all">Xで見る →</a>
    </div>
    <div style="background:#fff;border:1px solid #e0d8cc;border-radius:10px;padding:20px;margin-bottom:20px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
        <div style="width:40px;height:40px;border-radius:50%;background:#000;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <i class="ti ti-brand-x" aria-hidden="true" style="color:#fff;font-size:18px;"></i>
        </div>
        <div>
          <div style="font-size:13px;font-weight:500;color:#3c2e1e;">MKトラベル ツアー担当</div>
          <div style="font-size:11px;color:#999;">@mk_ryokou</div>
        </div>
      </div>
      <p style="font-size:13px;color:#5c4a32;line-height:1.8;margin-bottom:16px;">
        ツアー造成の裏側や京都の旬な情報を日々Xで発信しています。<br>
        ハッシュタグでツアーごとの投稿を確認できます。
      </p>
      <!-- ハッシュタグボタン -->
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;">
        <a href="https://x.com/search?q=%23MK%E3%83%84%E3%82%A2%E3%83%BC+from%3Amk_ryokou&f=live" target="_blank"
           style="background:#f5f0e8;color:#8b7355;padding:5px 12px;border-radius:20px;font-size:11px;text-decoration:none;border:1px solid #c5b8a8;">#MKツアー</a>
        <a href="https://x.com/search?q=%23%E7%A5%87%E5%9C%92%E7%A5%AD2026+from%3Amk_ryokou&f=live" target="_blank"
           style="background:#f5f0e8;color:#8b7355;padding:5px 12px;border-radius:20px;font-size:11px;text-decoration:none;border:1px solid #c5b8a8;">🎆 祇園祭2026</a>
        <a href="https://x.com/search?q=%23%E3%81%82%E3%81%98%E3%81%95%E3%81%842026+from%3Amk_ryokou&f=live" target="_blank"
           style="background:#f5f0e8;color:#8b7355;padding:5px 12px;border-radius:20px;font-size:11px;text-decoration:none;border:1px solid #c5b8a8;">🌸 あじさい2026</a>
        <a href="https://x.com/search?q=%23%E9%9E%8D%E9%A6%AC%E7%81%AB%E7%A5%AD2026+from%3Amk_ryokou&f=live" target="_blank"
           style="background:#f5f0e8;color:#8b7355;padding:5px 12px;border-radius:20px;font-size:11px;text-decoration:none;border:1px solid #c5b8a8;">🔥 鞍馬火祭2026</a>
        <a href="https://x.com/search?q=%23%E3%82%8D%E3%81%86%E3%81%9D%E3%81%8F%E3%81%BE%E3%81%A4%E3%82%8A2026+from%3Amk_ryokou&f=live" target="_blank"
           style="background:#f5f0e8;color:#8b7355;padding:5px 12px;border-radius:20px;font-size:11px;text-decoration:none;border:1px solid #c5b8a8;">🕯 ろうそくまつり2026</a>
        <a href="https://x.com/search?q=%23%E4%BA%94%E5%B1%B1%E9%80%81%E3%82%8A%E7%81%AC2026+from%3Amk_ryokou&f=live" target="_blank"
           style="background:#f5f0e8;color:#8b7355;padding:5px 12px;border-radius:20px;font-size:11px;text-decoration:none;border:1px solid #c5b8a8;">🏔 五山送り火2026</a>
      </div>
      <!-- Xで見るボタン -->
      <a href="https://x.com/mk_ryokou" target="_blank"
         style="display:flex;align-items:center;justify-content:center;gap:8px;background:#000;color:#fff;padding:10px;border-radius:8px;font-size:13px;font-weight:500;text-decoration:none;">
        <i class="ti ti-brand-x" aria-hidden="true" style="font-size:16px;"></i>
        @mk_ryokou の投稿をすべて見る
      </a>
    </div>

    <!-- 当日の様子 -->
    <div class="section-header" style="margin-top:16px">
      <div class="section-title"><i class="ti ti-camera" style="font-size:14px;vertical-align:-2px;margin-right:5px;"></i>当日の様子</div>
      <a href="#" class="see-all">すべての写真 →</a>
    </div>
    <div class="photo-grid">
      <a href="himatsuri2025.html" class="pt" style="position:relative;overflow:hidden;background:#1a1a1a;">
        <img src="https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/21f355c5596cd370e7f58f9c99c3b246-600x400.webp" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.85;" alt="鞍馬の火祭">
        <span style="position:absolute;bottom:8px;left:8px;color:#fff;font-size:11px;font-weight:500;text-shadow:0 1px 3px rgba(0,0,0,0.8);">🔥 鞍馬の火祭</span>
      </a>
      <div class="pt p2">嵐山ツアー</div>
      <div class="pt p3">ナイトハイク</div>
      <div class="pt p4">花手水</div>
      <div class="pt p5">新緑ハイク</div>
      <div class="p-upload"><i class="ti ti-cloud-upload"></i><span>写真を投稿</span></div>
    </div>
  </main>

  <!-- 右サイドバー -->
  <aside class="sidebar">
    <div class="sb-block">
      <div class="sb-title"><i class="ti ti-list-check" style="font-size:13px;vertical-align:-2px;margin-right:4px;"></i>直近の催行状況</div>
{sidebar_status}
    </div>
    <div class="sb-block">
      <div class="sb-title">SNS</div>
      <a href="https://page.line.me/620mozlm?openQrModal=true" target="_blank" class="sns-btn sns-line"><i class="ti ti-message-circle" style="font-size:15px"></i>LINE 友だち追加</a>
      <a href="https://x.com/mk_ryokou" target="_blank" class="sns-btn sns-x"><i class="ti ti-brand-x" style="font-size:15px"></i>X（ツアー担当）</a>
      <a href="https://www.instagram.com/mktravel.jp/" target="_blank" class="sns-btn sns-insta"><i class="ti ti-brand-instagram" style="font-size:15px"></i>Instagram</a>
      <a href="https://www.youtube.com/c/MKofficial_ch" target="_blank" class="sns-btn sns-youtube"><i class="ti ti-brand-youtube" style="font-size:15px"></i>YouTube</a>
    </div>
    <div class="sb-block">
      <div class="sb-title">過去のツアー</div>
      <a href="https://www.mk-group.co.jp/mktravel/list_008" target="_blank" class="past-item">📁 2026年</a>
      <a href="https://www.mk-group.co.jp/mktravel/list_008_2025" target="_blank" class="past-item">📁 2025年</a>
      <a href="https://www.mk-group.co.jp/mktravel/list_008_2024" target="_blank" class="past-item">📁 2024年</a>
    </div>
    <div class="sb-block" style="background:#fdf5e8;border-color:#e0c88a">
      <div style="font-size:12px;font-weight:500;color:#5c4a32;margin-bottom:5px">マイページ</div>
      <div style="font-size:12px;color:#7c5c2e;margin-bottom:8px">予約確認・お気に入り管理</div>
      <a href="https://www.mk-group.co.jp/mktravel/mypage" target="_blank" class="login-btn">ログイン</a>
    </div>

    <!-- 会社情報 -->
    <div class="sb-block" style="margin-top:4px;">
      <div class="sb-title">MKトラベル</div>
      <p style="font-size:11px;color:#7c5c2e;line-height:1.8;margin-bottom:10px;">
        京都発のご旅行はMKタクシーの旅行部門MKトラベルにご相談ください
      </p>
      <hr style="border:none;border-top:0.5px solid #e0d8cc;margin-bottom:10px;">
      <p style="font-size:11px;color:#999;line-height:1.8;margin-bottom:10px;">
        京都府知事登録第2-288<br>
        総合旅行業務取扱管理者<br>
        竹内雅哉
      </p>
      <a href="https://mk-group-form.spiral-site.com/mktravel_form" target="_blank"
         style="display:block;font-size:12px;font-weight:500;color:#5c4a32;margin-bottom:6px;">お問い合わせはこちら</a>
      <a href="https://www.mk-group.co.jp/mktravel/faq" target="_blank"
         style="display:block;font-size:12px;color:#5c4a32;margin-bottom:12px;">よくある質問はこちら</a>
      <hr style="border:none;border-top:0.5px solid #e0d8cc;margin-bottom:10px;">
      <a href="https://travel.mk-group.co.jp/tour-kiyaku/" target="_blank"
         style="display:block;font-size:11px;color:#8b7355;margin-bottom:5px;">募集型企画旅行規約</a>
      <a href="https://www.mk-group.co.jp/mktravel/tokusyo" target="_blank"
         style="display:block;font-size:11px;color:#8b7355;margin-bottom:5px;">特定商取引法に基づく表記</a>
      <a href="https://www.mk-group.co.jp/mktravel/pdf/ryokin.pdf" target="_blank"
         style="display:block;font-size:11px;color:#8b7355;margin-bottom:5px;">旅行業務取扱料金表</a>
      <a href="https://www.mk-group.co.jp/privacy/" target="_blank"
         style="display:block;font-size:11px;color:#8b7355;">プライバシーポリシー</a>
    </div>
  </aside>

</div><!-- /.page-wrap -->

<script>
  // ===== ツアーレポートデータ =====
  var TOUR_REPORTS = {tour_reports_js};

  function tourFilter(tag, el) {{
    var cards = document.querySelectorAll('.tour-card');
    var tabs  = document.querySelectorAll('.ftab');
    var count = 0;
    tabs.forEach(function(t) {{ t.classList.remove('active'); }});
    if (el) el.classList.add('active');
    cards.forEach(function(c) {{
      var tags = c.getAttribute('data-tags') || '';
      if (tag === 'all' || tags.indexOf(tag) !== -1) {{
        c.classList.remove('hidden'); count++;
      }} else {{
        c.classList.add('hidden');
      }}
    }});
    var note = document.getElementById('tour-count');
    if (note) note.textContent = count + '件のツアーを表示中';
  }}

  // 初期カウント表示
  window.addEventListener('load', function() {{
    var cards = document.querySelectorAll('.tour-card');
    var note  = document.getElementById('tour-count');
    if (note) note.textContent = cards.length + '件のツアーを表示中';
  }});

  function tourFilterByDate(dateKey) {{
    var cards = document.querySelectorAll('#tours-grid .tour-card');
    var count = 0;
    cards.forEach(function(card) {{
      var dates = (card.getAttribute('data-dates') || '').split(',');
      if (dates.indexOf(dateKey) !== -1) {{ card.classList.remove('hidden'); count++; }}
      else {{ card.classList.add('hidden'); }}
    }});
    document.querySelectorAll('.cd').forEach(function(c) {{ c.classList.remove('selected'); }});
    document.querySelectorAll('.cd').forEach(function(c) {{
      var parts = dateKey.split('-');
      var d = parts[2];
      if (c.textContent == String(parseInt(d)) &&
          (c.classList.contains('has-tour') || c.classList.contains('confirmed') ||
           c.classList.contains('full') || c.classList.contains('few'))) {{
        c.classList.add('selected');
      }}
    }});
    var note = document.getElementById('tour-filter-note');
    var mParts = dateKey.split('-');
    var label = mParts.length === 3 ? mParts[1] + '/' + mParts[2] : dateKey;
    if (note) {{ note.textContent = label + ' のツアーを表示中（' + count + '件）'; note.classList.add('show'); }}
    var reset = document.getElementById('tour-reset');
    if (reset) reset.style.display = 'inline';
    var noResult = document.getElementById('tour-no-result');
    if (noResult) noResult.style.display = count === 0 ? 'block' : 'none';
    var tabNote = document.getElementById('tour-count');
    if (tabNote) tabNote.textContent = count + '件のツアーを表示中';

    // ツアーレポート表示
    var reportSection = document.getElementById('tour-report-section');
    var reportPhotos  = document.getElementById('tour-report-photos');
    var reportLink    = document.getElementById('tour-report-link');
    if (reportSection && TOUR_REPORTS[dateKey]) {{
      var report = TOUR_REPORTS[dateKey];
      reportSection.style.display = 'block';
      reportLink.href = report.page;
      reportPhotos.innerHTML = '';
      report.photos.forEach(function(url) {{
        var a = document.createElement('a');
        a.href = report.page;
        a.style.cssText = 'border-radius:8px;overflow:hidden;aspect-ratio:1;display:block;';
        var img = document.createElement('img');
        img.src = url;
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block;';
        img.alt = report.title;
        a.appendChild(img);
        reportPhotos.appendChild(a);
      }});
    }} else if (reportSection) {{
      reportSection.style.display = 'none';
    }}
  }}

  function tourReset() {{
    document.querySelectorAll('#tours-grid .tour-card').forEach(function(c) {{ c.classList.remove('hidden'); }});
    document.querySelectorAll('.cd').forEach(function(c) {{ c.classList.remove('selected'); }});
    var note = document.getElementById('tour-filter-note');
    if (note) note.classList.remove('show');
    var reset = document.getElementById('tour-reset');
    if (reset) reset.style.display = 'none';
    var noResult = document.getElementById('tour-no-result');
    if (noResult) noResult.style.display = 'none';
    var cards = document.querySelectorAll('#tours-grid .tour-card');
    var tabNote = document.getElementById('tour-count');
    if (tabNote) tabNote.textContent = cards.length + '件のツアーを表示中';
    var reportSection = document.getElementById('tour-report-section');
    if (reportSection) reportSection.style.display = 'none';
  }}

  var TOUR = {{}};
{tour_js}

  var MN = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
  var DL = ['日','月','火','水','木','金','土'];
  var DC = ['cdl sun','cdl','cdl','cdl','cdl','cdl','cdl sat'];
  var CY = new Date().getFullYear();
  var CM = new Date().getMonth() + 1;

  function drawCal(y, m) {{
    var lbl  = document.getElementById('cal-month-label');
    var grid = document.getElementById('cal-grid-area');
    if (!lbl || !grid) {{ return; }}
    lbl.textContent = y + '年' + MN[m-1] + '　催行カレンダー';
    grid.innerHTML = '';
    for (var i = 0; i < 7; i++) {{
      var h = document.createElement('div');
      h.className = DC[i]; h.textContent = DL[i];
      grid.appendChild(h);
    }}
    var fd = new Date(y, m-1, 1).getDay();
    var ld = new Date(y, m, 0).getDate();
    var td = new Date();
    for (var i = 0; i < fd; i++) {{
      var b = document.createElement('div'); b.className = 'cd'; grid.appendChild(b);
    }}
    for (var d = 1; d <= ld; d++) {{
      var c = document.createElement('div');
      var k = y + '-' + m + '-' + d;
      var t = TOUR[k];
      var isT = (y === td.getFullYear() && m === td.getMonth()+1 && d === td.getDate());
      var cl = 'cd';
      if (t) {{ cl += t.st === 'confirmed' ? ' confirmed' : t.st === 'full' ? ' full' : ' has-tour'; }}
      if (isT) {{ cl += ' today'; }}
      c.className = cl;
      if (t) {{
        c.innerHTML = '<span style="display:block;text-align:center;">' + d + '</span><span style="display:block;text-align:right;font-size:9px;line-height:1;margin-top:-2px;">' + (t.em || '') + '</span>';
      }} else {{
        c.textContent = d;
      }}
      if (t) {{
        c.title = t.nt;
        c.style.cursor = 'pointer';
        (function(k) {{ c.onclick = function() {{ tourFilterByDate(k); }}; }})(k);
      }}
      grid.appendChild(c);
    }}
  }}

  function calMove(delta) {{
    CM += delta;
    if (CM > 12) {{ CM = 1; CY++; }}
    if (CM < 1)  {{ CM = 12; CY--; }}
    drawCal(CY, CM);
  }}

  drawCal(CY, CM);
</script>
</body>
</html>
"""


def generate(data_path: Path, output_path: Path) -> None:
    """tour_data.json を読み込んでindex.htmlを生成"""
    with open(data_path, "r", encoding="utf-8") as f:
        tours = json.load(f)

    updated_at = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    tour_js       = build_tour_js(tours)
    tour_cards    = build_tour_cards(tours)
    sidebar_status = build_sidebar_status(tours)

    # TOUR_REPORTSをJSオブジェクトに変換
    import json as _json
    tour_reports_js = _json.dumps(TOUR_REPORTS, ensure_ascii=False)

    html = HTML_TEMPLATE.format(
        updated_at=updated_at,
        tour_js=tour_js,
        tour_cards=tour_cards,
        sidebar_status=sidebar_status,
        tour_reports_js=tour_reports_js,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html を生成しました: {output_path}")


def main():
    base = Path(__file__).parent
    data_path   = base / "tour_data.json"
    output_path = base / "index.html"

    if not data_path.exists():
        print(f"❌ {data_path} が見つかりません。先に scraper.py を実行してください。")
        sys.exit(1)

    generate(data_path, output_path)


if __name__ == "__main__":
    main()
