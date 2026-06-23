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
# TOUR_REPORTSはtour_reports.jsonから読み込む
def _load_tour_reports():
    import json as _json2
    _path = Path(__file__).parent / "tour_reports.json"
    if _path.exists():
        with open(_path, "r", encoding="utf-8") as _f:
            return _json2.load(_f)
    return {}

TOUR_REPORTS = _load_tour_reports()

# ツアーキーワード→絵文字マッピング
# タグ → 絵文字マッピング（優先順位順）
TAG_EMOJI_MAP = [
    # お祭り・イベント
    ("イベント・お祭り", "🎇"),
    ("伝統文化",         "🎇"),
    ("ナイトツアー",     "🎇"),
    # 季節の花
    ("季節の花",         "🌸"),
    # 歴史・寺社巡り
    ("歴史",             "🏯"),
    ("神社仏閣",         "🏯"),
    # 体験・名所めぐり（上記に当てはまらない場合）
    ("グルメ",           "💜"),
    ("体験",             "💜"),
    ("ガイド・講座",     "💜"),
    ("景色・写真",       "💜"),
]

def get_emoji_from_tags(tags: list) -> str:
    """タグリストから絵文字を1つ返す（優先順位順）"""
    for tag_kw, emoji in TAG_EMOJI_MAP:
        if tag_kw in tags:
            return emoji
    return "💜"  # デフォルト

def get_tour_emoji(title: str) -> str:
    """後方互換用（タイトルからは絵文字を返さない）"""
    return "💜"

def build_tour_js(tours: dict) -> str:
    """tour_data.json からカレンダー用JSデータを生成"""
    lines = []
    SKIP_KEYS = {"uma", "yokokuji_shuttle", "shojuin_sogei", "narihira_nishiyama", "momidiya"}

    import datetime as _dt2, re as _re2
    for key, tour in tours.items():
        if key in SKIP_KEYS:
            continue
        if tour.get("hidden"):
            continue  # 手動非表示フラグ
        if tour.get("error"):
            continue
        url = tour["url"]
        title = tour["title"].replace("'", "\\'")
        tags = tour.get("tags", [])

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
            emoji = get_emoji_from_tags(tags)
            # 既存エントリに絵文字を追加（同じ日付に複数ツアーがある場合）
            existing_idx = None
            for i, line in enumerate(lines):
                if f"TOUR['{k}']" in line:
                    existing_idx = i
                    break
            if existing_idx is not None:
                import re as _re
                # 絵文字を追加
                m2 = _re.search(r"em:'([^']*)'", lines[existing_idx])
                if m2:
                    existing_em = m2.group(1)
                    if emoji and emoji not in existing_em:
                        lines[existing_idx] = lines[existing_idx].replace(
                            f"em:'{existing_em}'", f"em:'{existing_em}{emoji}'"
                        )
                # ステータスの優先順位：full > confirmed > few > tour
                priority = {'confirmed': 3, 'full': 2, 'few': 1, 'tour': 0}
                m3 = _re.search(r"st:'([^']*)'", lines[existing_idx])
                if m3:
                    existing_st = m3.group(1)
                    if priority.get(t, 0) > priority.get(existing_st, 0):
                        lines[existing_idx] = lines[existing_idx].replace(
                            f"st:'{existing_st}'", f"st:'{t}'"
                        )
            else:
                lines.append(
                    f"      TOUR['{k}'] = {{st:'{t}', ti:'{title}', ur:{var_url}, nt:'{note}', em:'{emoji}'}};"
                )

    # 随時催行ツアー（ALWAYS_ON_TOURS）をJSに追加（通常ツアー処理の後）
    import datetime as _dtt
    ALWAYS_ON_TOURS = {
        "uma": {"start": (2026,1,1), "end": (2026,12,31), "status": "tour"},
        "yokokuji_shuttle": {"start": (2026,1,1), "end": (2026,12,31), "status": "tour"},
        "shojuin_sogei":    {"start": (2026,1,1), "end": (2026,12,31), "status": "tour", "weekdays": {3,4,5,6}},
        "narihira_nishiyama": {"start": (2026,1,1), "end": (2026,12,31), "status": "tour"},
        "momidiya":            {"start": (2026,6,1), "end": (2026,9,30), "status": "tour"},
    }
    for akey, aval in ALWAYS_ON_TOURS.items():
        if akey not in tours:
            continue
        atour = tours[akey]
        atitle = atour.get("title", "")
        aurl   = atour.get("url", "")
        atags = atour.get("tags", [])
        aemoji = get_emoji_from_tags(atags)
        var_url2 = f"_u_{akey.replace('-','_')}"
        lines.append(f"      var {var_url2} = '{aurl}';")
        sy, sm, sd = aval["start"]
        ey, em2, ed = aval["end"]
        cur = _dtt.date(sy, sm, sd)
        end_d = _dtt.date(ey, em2, ed)
        weekdays = aval.get("weekdays", None)  # Noneなら全日
        while cur <= end_d:
            if weekdays is None or cur.weekday() in weekdays:
                pass
            else:
                cur += _dtt.timedelta(days=1)
                continue
            k = f"{cur.year}-{cur.month}-{cur.day}"
            existing_idx = None
            for i, line in enumerate(lines):
                if f"TOUR['{k}']" in line:
                    existing_idx = i
                    break
            if existing_idx is not None:
                import re as _re
                m2 = _re.search(r"em:'([^']*)'", lines[existing_idx])
                if m2 and aemoji and aemoji not in m2.group(1):
                    lines[existing_idx] = lines[existing_idx].replace(
                        f"em:'{m2.group(1)}'", f"em:'{m2.group(1)}{aemoji}'"
                    )
            else:
                lines.append(f"      TOUR['{k}'] = {{st:'tour', ti:'{atitle}', ur:{var_url2}, nt:'{atitle}', em:'{aemoji}'}};")
            cur += _dtt.timedelta(days=1)

    return "\n".join(lines)


def build_tour_cards(tours: dict) -> str:
    """tour_data.json からツアーカードHTMLを生成"""

    # カテゴリタグ判定
    def get_tag_class(tags: list) -> tuple:
        """タグリストからCSSクラスとラベルを返す（最大2つ）"""
        mapping = {
            "イベント": ("tev", "イベント・お祭り"),
            "お祭り":   ("tev", "イベント・お祭り"),
            "伝統":     ("tev", "イベント・お祭り"),
            "ナイト":   ("tev", "イベント・お祭り"),
            "歴史":     ("th",  "歴史・社寺巡り"),
            "社寺":     ("th",  "歴史・社寺巡り"),
            "神社":     ("th",  "歴史・社寺巡り"),
            "体験":     ("te",  "体験・名所巡り"),
            "名所":     ("te",  "体験・名所巡り"),
            "景色":     ("te",  "体験・名所巡り"),
            "グルメ":   ("te",  "体験・名所巡り"),
            "ガイド":   ("te",  "体験・名所巡り"),
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
    def get_badge(statuses: list, dates: list = None) -> tuple:
        """最も重要なステータスのバッジを返す (class, text)"""
        if not statuses:
            return ("br", "募集中")
        types = [s["type"] for s in statuses]
        if "confirmed" in types:
            # 出発日が1日のみの場合は「催行確定」、複数の場合は「催行確定日あり」
            if dates is not None:
                valid_dates = [d for d in dates if re.search(r'\d+/\d+', d) and '～' not in d and not d.startswith('※') and '随時' not in d]
                if len(valid_dates) == 1:
                    return ("bc", "催行確定")
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
    cards_entries = []  # (sort_key, html) のリスト
    SKIP_KEYS = {"uma", "yokokuji_shuttle", "shojuin_sogei", "narihira_nishiyama", "momidiya"}

    import datetime as _dt2, re as _re2
    _today = _dt2.date.today()

    def is_all_past(tour):
        """全日程が過去ならTrueを返す（随時催行はFalse）"""
        dates = tour.get("dates", [])
        if not dates: return False
        future_found = False
        date_found = False
        for d in dates:
            if "随時" in str(d): return False
            for m in _re2.finditer(r"(\d{1,2})/(\d{1,2})", str(d)):
                mo, day = int(m.group(1)), int(m.group(2))
                try:
                    dt = _dt2.date(_today.year, mo, day)
                    date_found = True
                    if dt >= _today: future_found = True
                except: pass
            period = _re2.search(r"(\d{1,2})/(\d{1,2}).*?[～~].*(\d{1,2})/(\d{1,2})", str(d))
            if period:
                mo2, day2 = int(period.group(3)), int(period.group(4))
                try:
                    dt2 = _dt2.date(_today.year, mo2, day2)
                    date_found = True
                    if dt2 >= _today: future_found = True
                except: pass
        if not date_found: return False
        return not future_found

    for i, (key, tour) in enumerate(tours.items()):
        if key in SKIP_KEYS:
            continue
        if is_all_past(tour):
            continue  # 全日程が過去のツアーは非表示
        if tour.get("hidden"):
            continue  # 手動非表示フラグ
        if "募集終了" in tour.get("title", "") or "受付終了" in tour.get("title", ""):
            continue  # タイトルに【募集終了】が含まれるツアーは非表示
        if tour.get("error"):
            # エラーの場合は準備中カード
            cards_entries.append((_dt2.date(9999,12,31), f"""      <div class="tour-card" style="opacity:0.55;">
        <div class="tour-img" style="background:#b0a090;">
          <div style="padding:10px;text-align:center;">取得エラー<br><small>{tour['url']}</small></div>
          <div class="sbadge br">取得失敗</div>
        </div>
        <div class="tour-body">
          <div class="tour-title">データ取得に失敗しました</div>
          <div class="tour-date">—</div>
          <span class="btn-detail" style="background:#b0a090;cursor:default;">エラー</span>
        </div>
      </div>"""))
            continue

        title    = tour["title"]
        url      = tour["url"]
        image    = tour.get("image", "")
        price    = tour.get("price", "")
        tags     = tour.get("tags", [])
        statuses = tour.get("statuses", [])
        dates    = tour.get("dates", [])

        tag_items = get_tag_class(tags)
        badge_cls, badge_text = get_badge(statuses, dates)
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
            if 'イベント' in t or 'お祭り' in t or '伝統' in t or 'ナイト' in t: filter_tags.append('event')
            if '体験' in t or '名所' in t or '景色' in t or 'グルメ' in t or 'ガイド' in t: filter_tags.append('exp')
            if '歴史' in t or '社寺' in t or '神社' in t:       filter_tags.append('history')
            if '季節' in t or '花' in t:                        filter_tags.append('flower')
            if '夏' in t:                                       filter_tags.append('summer')
            if '秋' in t:                                       filter_tags.append('autumn')
            if '冬' in t:                                       filter_tags.append('winter')
            if '春' in t:                                       filter_tags.append('spring')
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

        # ソートキー：最も近い未来の日付を取得
        _sort_key = _dt2.date(9999,12,30)  # デフォルトは末尾（随時催行の前）
        for _sd in statuses:
            _parsed = parse_date(_sd.get("date",""))
            if _parsed:
                _y,_m,_d = _parsed
                _dt_val = _dt2.date(_y,_m,_d)
                if _dt_val >= _today and _dt_val < _sort_key:
                    _sort_key = _dt_val
        for _dd in dates:
            import re as _re3
            for _mm in _re3.finditer(r"(\d{1,2})/(\d{1,2})", str(_dd)):
                try:
                    _dt_val = _dt2.date(_today.year, int(_mm.group(1)), int(_mm.group(2)))
                    if _dt_val >= _today and _dt_val < _sort_key:
                        _sort_key = _dt_val
                except: pass

        cards_entries.append((_sort_key, f"""      <div class="tour-card" data-tags="{data_tags}" data-dates="{data_dates_attr}">
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
      </div>"""))

    # 随時催行ツアーのカードを追加（スクレイパーカードは除外）
    ALWAYS_ON_KEYS = ["uma", "yokokuji_shuttle", "shojuin_sogei", "narihira_nishiyama", "momidiya"]
    SKIP_KEYS = set(ALWAYS_ON_KEYS)  # 通常カードには表示しない
    for akey in ALWAYS_ON_KEYS:
        if akey not in tours:
            continue
        t = tours[akey]
        title = t.get("title", "")
        url   = t.get("url", "")
        img   = t.get("image", "")
        price = t.get("price", "")
        tags  = t.get("tags", [])
        tag_classes = get_tag_class(tags)
        tags_html = "".join(f'<span class="ttag {c}">{l}</span>' for c, l in tag_classes)
        # 随時催行カードはすべてのカテゴリタブで表示されるよう"all"相当にする
        data_tags = "event exp history flower summer autumn other"
        img_html = (f'<img src="{img}" alt="{title}" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;object-position:50% 30%;" onerror="this.style.display=\'none\'">') if img else ""
        cards_entries.append((_dt2.date(9999,12,31), f"""      <div class="tour-card" data-tags="{data_tags}" data-dates="">
        <div class="tour-img" style="background:#7c6b4a;position:relative;overflow:hidden;">
          {img_html}
          <div class="sbadge br" style="z-index:1;">随時催行</div>
        </div>
        <div class="tour-body">
          <div class="tour-tags">{tags_html}</div>
          <div class="tour-title">{title}</div>
          <div class="tour-date">随時催行</div>
          <div class="tour-price">大人1名 {price}</div>
          <a href="{url}" target="_blank" class="btn-detail">詳細をみる</a>
        </div>
      </div>"""))

    # 日付近い順→随時催行の順にソート
    cards_entries.sort(key=lambda x: x[0])
    return "\n".join(html for _, html in cards_entries)


def build_sidebar_status(tours: dict) -> str:
    """直近の催行状況リストを生成（今日以降のみ・日付近い順）"""
    import datetime as _dt, re as _re
    today = _dt.date.today()

    def parse_date(date_str):
        try:
            m = _re.search(r"(\d+)/(\d+)", date_str)
            if not m: return None
            mo, d = int(m.group(1)), int(m.group(2))
            dt = _dt.date(today.year, mo, d)
            if dt < today: return None  # 過去日付は除外
            return dt
        except: return None

    entries = []
    SKIP_KEYS = {"uma", "yokokuji_shuttle", "shojuin_sogei", "narihira_nishiyama", "momidiya"}
    for key, tour in tours.items():
        if key in SKIP_KEYS: continue
        if tour.get("hidden"): continue  # 手動非表示フラグ
        if tour.get("error"): continue
        title_short = tour["title"][:12] + ("…" if len(tour["title"]) > 12 else "")
        url = tour.get("url", "#")
        statuses = tour.get("statuses", [])
        if not statuses:
            entries.append((_dt.date(9999,12,31), "tour",
                f'      <a href="{url}" target="_blank" class="status-item" style="text-decoration:none;">'  
                f'<span class="sname">{title_short}</span>'
                f'<span class="stag" style="background:#2980b9;color:#fff">募集中</span></a>'))
            continue
        confirmed = [s for s in statuses if s["type"] == "confirmed"]
        full_list = [s for s in statuses if s["type"] == "full"]
        few_list  = [s for s in statuses if s["type"] == "few"]
        if confirmed:
            s = confirmed[0]; dt = parse_date(s["date"])
            if dt and dt >= today:
                entries.append((dt, "confirmed",
                    f'      <a href="{url}" target="_blank" class="status-item" style="text-decoration:none;">'
                    f'<span class="sname">{title_short} {s["date"]}</span>'
                    f'<span class="stag" style="background:#27ae60;color:#fff">催行確定</span></a>'))
        elif full_list:
            s = full_list[0]; dt = parse_date(s["date"])
            if dt and dt >= today:
                entries.append((dt, "full",
                    f'      <a href="{url}" target="_blank" class="status-item full-s" style="text-decoration:none;">'
                    f'<span class="sname">{title_short} {s["date"]}</span>'
                    f'<span class="stag" style="background:#c0392b;color:#fff">満席</span></a>'))
        elif few_list:
            s = few_list[0]; dt = parse_date(s["date"])
            if dt and dt >= today:
                entries.append((dt, "few",
                    f'      <a href="{url}" target="_blank" class="status-item" style="text-decoration:none;">'
                    f'<span class="sname">{title_short} {s["date"]}</span>'
                    f'<span class="stag" style="background:#e67e22;color:#fff">{s["label"]}</span></a>'))
    entries.sort(key=lambda x: x[0])
    return "\n".join(e[2] for e in entries[:5])

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
    .hero {{ background: #faf8f5; color: #fff; padding: 28px 24px; text-align: center; position: relative; }}
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
    .season-popup-overlay {{ display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:9999;align-items:center;justify-content:center; }}
    .season-popup-overlay.show {{ display:flex; }}
    .season-popup {{ background:#fff;border-radius:12px;overflow:hidden;max-width:420px;width:90%; }}
    .season-popup img {{ width:100%;height:220px;object-fit:cover;display:block; }}
    .season-popup-body {{ padding:16px; }}
    .season-popup-title {{ font-size:14px;font-weight:500;color:#3c2e1e;margin-bottom:8px; }}
    .season-popup-desc {{ font-size:12px;color:#7c6040;line-height:1.7;margin-bottom:12px; }}
    .season-popup-btn {{ display:block;text-align:center;background:#8b7355;color:#fff;border-radius:6px;padding:9px;font-size:13px;font-weight:500;margin-bottom:8px; }}
    .season-popup-btn:hover {{ background:#7a6448; }}
    .season-popup-close {{ display:block;text-align:center;font-size:12px;color:#999;cursor:pointer; }}
    .bnav-season-label {{ display:flex;align-items:center;justify-content:space-between;padding:7px 14px 7px 22px;font-size:11px;color:#7c6040;cursor:pointer;font-weight:500; }}
    .bnav-season-label:hover {{ background:#f0ebe2;color:#5c4a32; }}
    .bnav-season-label.open {{ color:#8b7355;background:#f5ede0; }}
    .bnav-season-label.open i {{ transform:rotate(90deg); }}
    .bnav-season-label i {{ transition:transform 0.2s; }}
    .bnav-season-body {{ display:none;padding:0 8px 6px; }}
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
    .cd {{ text-align: center; font-size: 13px; padding: 14px 2px; border-radius: 5px; cursor: pointer; }}
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
    .cd.selected {{ outline: 2px solid #e8a0b0; outline-offset: -2px; }}
    .cd-paw {{ display: none; filter: sepia(1) saturate(3) hue-rotate(300deg) brightness(1.3); font-size: 26px; line-height: 1; text-align: center; }}
    .filter-note {{ font-size: 12px; color: var(--color-text-secondary, #888); background: #f5f0e8; border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; display: none; }}
    .filter-note.show {{ display: block; }}
    .reset-link {{ font-size: 12px; color: #8b7355; cursor: pointer; text-decoration: underline; display: none; }}
    .tour-card {{ background: #fff; border: 1px solid #d0c4b0; border-radius: 10px; overflow: hidden; transition: box-shadow 0.2s; }}
    .tour-card:hover {{ box-shadow: 0 2px 10px rgba(139,115,85,0.15); }}
    .tour-img {{ width: 100%; height: 200px; position: relative; overflow: hidden; font-size: 13px; color: #fff; font-weight: 500; background: #1a1a1a; }}
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
    .article-modal-overlay {{ display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9998;align-items:center;justify-content:center; }}
    .article-modal-overlay.show {{ display:flex; }}
    .article-modal {{ background:#fff;border-radius:12px;max-width:680px;width:90%;max-height:85vh;overflow-y:auto;padding:24px;position:relative; }}
    .article-modal-close {{ position:absolute;top:12px;right:16px;font-size:20px;cursor:pointer;color:#999; }}
    .news-body {{ display:flex; gap:14px; align-items:flex-start; }}
    .news-photo {{ flex:0 0 220px; max-width:220px; }}
    .news-photo img {{ width:100%; border-radius:6px; object-fit:cover; height:160px; }}
    .news-photos {{ display:grid; grid-template-columns:repeat(3,1fr); gap:6px; margin-top:10px; }}
    .news-photos img {{ width:100%; border-radius:6px; object-fit:cover; aspect-ratio:4/3; }}
    @media (max-width: 600px) {{
      .news-body {{ flex-direction:column; }}
      .news-photo {{ flex:none; max-width:100%; width:100%; }}
      .news-photo img {{ height:200px; width:100%; }}
    }}
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
    .sp-tabs {{ display:none; }}
    .sp-panel {{ display:none; }}
    @media (max-width: 900px) {{
      .sp-tabs {{
        display:flex;
        background:#faf8f5;
        border-bottom:2px solid #e0d8cc;
        position:sticky;top:0;z-index:99;
        overflow-x:auto;
      }}
      .sp-tab {{
        flex:1;min-width:80px;padding:10px 6px;text-align:center;font-size:12px;
        color:#8b7355;font-weight:500;cursor:pointer;white-space:nowrap;
        border-bottom:3px solid transparent;
      }}
      .sp-tab.active {{ border-bottom-color:#8b7355;color:#5c4a32; }}
      .sp-panel {{ display:none;background:#faf8f5;border-bottom:1px solid #e0d8cc;padding:12px 16px; }}
      .sp-panel.active {{ display:block; }}
      .sp-panel .bnav-sub {{ display:block; }}
      .sp-panel .bnav-cat-label {{ display:none; }}
      .sp-panel .bnav-season-body {{ display:none; }}
    }}
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
         style="width:100%;height:100%;object-fit:cover;opacity:0.15;">
  </div>
  <div style="position:relative;z-index:1;">
    <img src="https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/logoblack.png" alt="MKグループ" style="height:40px;margin-bottom:8px;">
    <h1 style="color:#8b7355;">旅とも手帳</h1>
    <p style="color:#8b7355;">ＭＫが案内する、ここだけの京都</p>
  </div>
</div>

<!-- スマホ用タブナビ -->
<div class="sp-tabs" id="sp-tabs">
  <div class="sp-tab active" onclick="spTab('diary', this)">📔 造成日記</div>
  <div class="sp-tab" onclick="spTab('season', this)">🌸 季節・テーマ</div>
  <div class="sp-tab" onclick="spTab('past', this)">📁 過去のツアー</div>
</div>
<div class="sp-panel active" id="sp-diary">
  <a href="#" onclick="filterArticles('all',this);closeSp();" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">すべて</a>
  <a href="#" onclick="filterArticles('New！',this);closeSp();" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">New！</a>
  <a href="#" onclick="filterArticles('企画のたまご',this);closeSp();" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">企画のたまご</a>
  <a href="#" onclick="filterArticles('レポート',this);closeSp();" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">レポート</a>
  <a href="#" onclick="filterArticles('完成！',this);closeSp();" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">完成！</a>
</div>
<div class="sp-panel" id="sp-season">
  <div style="font-size:12px;color:#8b7355;font-weight:500;padding:4px 0;">🌸 春の京都</div>
  <a href="#" onclick="openSeasonPopup('sakura');closeSp();" style="display:block;padding:4px 0 4px 12px;font-size:12px;color:#5c4a32;">美山・大野ダム</a>
  <div style="font-size:12px;color:#8b7355;font-weight:500;padding:4px 0;margin-top:6px;">☀️ 夏祭り</div>
  <a href="#" onclick="openSeasonPopup('furin');closeSp();" style="display:block;padding:4px 0 4px 12px;font-size:12px;color:#5c4a32;">風鈴まつり</a>
  <a href="#" onclick="openSeasonPopup('maizuru');closeSp();" style="display:block;padding:4px 0 4px 12px;font-size:12px;color:#5c4a32;">海とあじさいの絶景</a>
  <div style="font-size:12px;color:#8b7355;font-weight:500;padding:4px 0;margin-top:6px;">🍁 紅葉の秋</div>
  <a href="#" onclick="openSeasonPopup('himatsuri');closeSp();" style="display:block;padding:4px 0 4px 12px;font-size:12px;color:#5c4a32;">鞍馬の火祭</a>
  <div style="font-size:12px;color:#8b7355;font-weight:500;padding:4px 0;margin-top:6px;">❄️ 冬の情緒</div>
</div>
<div class="sp-panel" id="sp-past">
  <a href="https://www.mk-group.co.jp/mktravel/list_008" target="_blank" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">📁 2026年</a>
  <a href="https://www.mk-group.co.jp/mktravel/list_008_2025" target="_blank" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">📁 2025年</a>
  <a href="https://www.mk-group.co.jp/mktravel/list_008_2024" target="_blank" style="display:block;padding:6px 0;font-size:13px;color:#5c4a32;">📁 2024年</a>
</div>

<p class="updated-note">最終更新: {updated_at}</p>

<div class="page-wrap">

  <!-- 左：ブログナビ -->
  <aside class="blog-nav">
    <div class="blog-nav-title"><i class="ti ti-notebook"></i>ツアー日記</div>
    <div class="bnav-category">
      <div class="bnav-cat-label">造成日記</div>
      <div class="bnav-sub">
        <a href="#" onclick="filterArticles('all', this)"><i class="ti ti-chevron-right"></i>すべて</a>
        <div class="bnav-season-label" onclick="toggleSeason(this)" id="new-label">
          <span style="display:flex;align-items:center;gap:4px;"><i class="ti ti-chevron-right" style="font-size:11px;"></i>New！</span>

        </div>
        <div class="bnav-season-body" id="new-articles-body">
          {new_articles_nav}
        </div>
        <div class="bnav-season-label" onclick="toggleSeason(this)" id="tamago-label">
          <span style="display:flex;align-items:center;gap:4px;"><i class="ti ti-chevron-right" style="font-size:11px;"></i>企画のたまご</span>
        </div>
        <div class="bnav-season-body" id="tamago-articles-body">
          {tamago_links}
        </div>
        <div class="bnav-season-label" onclick="toggleSeason(this)" id="report-label">
          <span style="display:flex;align-items:center;gap:4px;"><i class="ti ti-chevron-right" style="font-size:11px;"></i>レポート</span>
        </div>
        <div class="bnav-season-body" id="report-articles-body">
          {report_links}
        </div>
        <div class="bnav-season-label" onclick="toggleSeason(this)" id="done-label">
          <span style="display:flex;align-items:center;gap:4px;"><i class="ti ti-chevron-right" style="font-size:11px;"></i>完成！</span>
        </div>
        <div class="bnav-season-body" id="done-articles-body">
          {done_links}
        </div>
      </div>
    </div>
    <div class="bnav-category">
      <div class="bnav-cat-label">季節・テーマ</div>
      <div class="bnav-sub" style="padding:4px 0;">
        <!-- 春の京都 -->
        <div class="bnav-season-label" onclick="toggleSeason(this)">
          <span>🌸 春の京都</span><i class="ti ti-chevron-right" style="font-size:11px;"></i>
        </div>
        <div class="bnav-season-body">
          <div onclick="openSeasonPopup('sakura')" style="display:block;border-radius:6px;overflow:hidden;margin-bottom:4px;cursor:pointer;">
            <div style="position:relative;height:60px;overflow:hidden;border-radius:6px;">
              <img src="https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/250409_oonodam%20dr%20teramoto.jpg" style="width:100%;height:100%;object-fit:cover;object-position:center top;display:block;">
              <div style="position:absolute;inset:0;background:linear-gradient(transparent,rgba(0,0,0,0.5));"></div>
              <span style="position:absolute;bottom:4px;left:7px;color:#fff;font-size:10px;font-weight:500;">🌸 美山・大野ダム</span>
            </div>
          </div>
        </div>
        <!-- 夏祭り -->
        <div class="bnav-season-label" onclick="toggleSeason(this)">
          <span>☀️ 夏祭り</span><i class="ti ti-chevron-right" style="font-size:11px;"></i>
        </div>
        <div class="bnav-season-body">
          <div onclick="openSeasonPopup('furin')" style="display:block;border-radius:6px;overflow:hidden;margin-bottom:4px;cursor:pointer;">
            <div style="position:relative;height:60px;overflow:hidden;border-radius:6px;">
              <img src="https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/250707_%E6%AD%A3%E5%AF%BF%E9%99%A2_%E9%A2%A8%E9%88%B4%E3%81%BE%E3%81%A4%E3%82%8A-%E8%A5%BF%E5%B7%9D%20(6).jpg" style="width:100%;height:100%;object-fit:cover;object-position:center top;display:block;">
              <div style="position:absolute;inset:0;background:linear-gradient(transparent,rgba(0,0,0,0.5));"></div>
              <span style="position:absolute;bottom:4px;left:7px;color:#fff;font-size:10px;font-weight:500;">🔔 風鈴まつり</span>
            </div>
          </div>
          <div onclick="openSeasonPopup('maizuru')" style="display:block;border-radius:6px;overflow:hidden;margin-bottom:4px;cursor:pointer;">
            <div style="position:relative;height:60px;overflow:hidden;border-radius:6px;">
              <img src="https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/20260620%20dr%20mishimura.jpg" style="width:100%;height:100%;object-fit:cover;object-position:center top;display:block;">
              <div style="position:absolute;inset:0;background:linear-gradient(transparent,rgba(0,0,0,0.5));"></div>
              <span style="position:absolute;bottom:4px;left:7px;color:#fff;font-size:10px;font-weight:500;">🌊 海とあじさいの絶景</span>
            </div>
          </div>
        </div>
        <!-- 紅葉の秋 -->
        <div class="bnav-season-label" onclick="toggleSeason(this)">
          <span>🍁 紅葉の秋</span><i class="ti ti-chevron-right" style="font-size:11px;"></i>
        </div>
        <div class="bnav-season-body">
          <div onclick="openSeasonPopup('himatsuri')" style="display:block;border-radius:6px;overflow:hidden;margin-bottom:4px;cursor:pointer;">
            <div style="position:relative;height:60px;overflow:hidden;border-radius:6px;background:#3a2a1a;">
              <img src="https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/21f355c5596cd370e7f58f9c99c3b246-600x400.webp" style="width:100%;height:100%;object-fit:cover;object-position:center top;display:block;opacity:0.85;">
              <div style="position:absolute;inset:0;background:linear-gradient(transparent,rgba(0,0,0,0.5));"></div>
              <span style="position:absolute;bottom:4px;left:7px;color:#fff;font-size:10px;font-weight:500;">🔥 鞍馬の火祭</span>
            </div>
          </div>
        </div>
        <!-- 冬の情緒 -->
        <div class="bnav-season-label" onclick="toggleSeason(this)">
          <span>❄️ 冬の情緒</span><i class="ti ti-chevron-right" style="font-size:11px;"></i>
        </div>
        <div class="bnav-season-body"></div>
      </div>
    </div>

    <div class="bnav-category" style="border-bottom:none">
      <div class="bnav-cat-label">過去のツアー</div>
      <div class="bnav-sub">
        <a href="https://www.mk-group.co.jp/mktravel/list_008" target="_blank"><i class="ti ti-chevron-right"></i>📁 2026年</a>
        <a href="https://www.mk-group.co.jp/mktravel/list_008_2025" target="_blank"><i class="ti ti-chevron-right"></i>📁 2025年</a>
        <a href="https://www.mk-group.co.jp/mktravel/list_008_2024" target="_blank"><i class="ti ti-chevron-right"></i>📁 2024年</a>
      </div>
    </div>

  </aside>

  <!-- 中央：メインコンテンツ -->
  <main class="content">
    <!-- 造成日記 -->
    <div id="article-section" style="margin-bottom:16px;display:none;">
      <div class="section-header">
        <div class="section-title">
          <i class="ti ti-notebook" style="font-size:14px;vertical-align:-2px;margin-right:5px;"></i>
          ツアー日記 / 担当者からのお知らせ
        </div>
      </div>
      {articles_html}
    </div>

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
      <div class="cal-legend" style="margin-top:10px;">
        <div class="cl-item"><div class="cl-dot" style="background:#f0e8d8;border:1px solid #c5b8a8;"></div>ツアーあり</div>
        <div class="cl-item"><div class="cl-dot" style="background:#8b7355;"></div>催行確定</div>
        <div class="cl-item"><div class="cl-dot" style="background:#c0392b;"></div>満席</div>
        <div class="cl-item"><div class="cl-dot" style="outline:2px solid #8b7355;outline-offset:-1px;"></div>本日</div>
      </div>
      <p style="font-size:11px;color:#999;margin-top:8px;">※色付き日付をクリックするとツアー詳細ページを開きます</p>
      <!-- 直近の催行状況（カレンダー下） -->
      <div style="margin-top:14px;border-top:1px solid #e0d8cc;padding-top:12px;">
        <div style="font-size:13px;font-weight:500;color:#5c4a32;margin-bottom:8px;"><i class="ti ti-list-check" style="font-size:13px;vertical-align:-2px;margin-right:4px;"></i>直近の催行状況</div>
        {sidebar_status}
      </div>
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
      <div class="ftab" onclick="tourFilter('winter', this)">冬のツアー</div>
      <div class="ftab" onclick="tourFilter('spring', this)">春のツアー</div>
    </div>
    <div class="filter-tabs" style="margin-top:-4px;">
      <div class="ftab" onclick="tourFilterStatus('confirmed', this)">✅ 催行確定</div>
      <div class="ftab" onclick="tourFilterStatus('full', this)">🈵 満席</div>
      <div class="ftab" onclick="tourFilterStatus('recruiting', this)">📢 募集中</div>
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
      <div class="sb-title">SNS</div>
      <a href="https://page.line.me/620mozlm?openQrModal=true" target="_blank" class="sns-btn sns-line"><i class="ti ti-message-circle" style="font-size:15px"></i>LINE 友だち追加</a>
      <a href="https://x.com/mk_ryokou" target="_blank" class="sns-btn sns-x"><i class="ti ti-brand-x" style="font-size:15px"></i>X（ツアー担当）</a>
      <a href="https://www.instagram.com/mktravel.jp/" target="_blank" class="sns-btn sns-insta"><i class="ti ti-brand-instagram" style="font-size:15px"></i>Instagram</a>
      <a href="https://www.youtube.com/c/MKofficial_ch" target="_blank" class="sns-btn sns-youtube"><i class="ti ti-brand-youtube" style="font-size:15px"></i>YouTube</a>
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

<!-- 記事モーダル -->
<div class="article-modal-overlay" id="article-modal-overlay" onclick="closeArticleModal()">
  <div class="article-modal" onclick="event.stopPropagation()">
    <span class="article-modal-close" onclick="closeArticleModal()">✕</span>
    <div id="article-modal-content"></div>
  </div>
</div>

<!-- 季節テーマ ポップアップ -->
<div class="season-popup-overlay" id="season-popup-overlay" onclick="closeSeasonPopup()">
  <div class="season-popup" onclick="event.stopPropagation()">
    <img id="sp-img" src="" alt="">
    <div class="season-popup-body">
      <div class="season-popup-title" id="sp-title"></div>
      <div id="sp-date" style="display:none;font-size:11px;color:#8b7355;margin-bottom:8px;background:#fdf5e8;padding:4px 8px;border-radius:4px;display:inline-block;"></div>
      <div class="season-popup-desc" id="sp-desc" style="margin-top:8px;"></div>
      <div id="sp-btn-wrap"></div>
      <span class="season-popup-close" onclick="closeSeasonPopup()">閉じる ×</span>
    </div>
  </div>
</div>

<script>
  // ===== ツアーレポートデータ =====
  var TOUR_REPORTS = {tour_reports_js};

  // ===== 季節テーマ ポップアップ =====
  var SEASON_DATA = {{
    'sakura': {{
      img: 'https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/250409_oonodam%20dr%20teramoto.jpg',
      title: '美山・大野ダム',
      date: '📷 2025年4月9日 ドライバー寺本撮影',
      desc: '春の美山、大野ダムのほとりに咲く桜。青い水面と山々を背景に、白とピンクの桜が美しく広がります。',
      links: []
    }},
    'furin': {{
      img: 'https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/250707_%E6%AD%A3%E5%AF%BF%E9%99%A2_%E9%A2%A8%E9%88%B4%E3%81%BE%E3%81%A4%E3%82%8A-%E8%A5%BF%E5%B7%9D%20(6).jpg',
      title: '正寿院 風鈴まつり送迎プラン 2026',
      date: '📷 2025年7月7日 ドライバー撮影',
      desc: '6月〜9月の週末を中心に開催。色とりどりの風鈴が境内を彩る正寿院の夏。京都駅・宇治駅から送迎付きのお手軽プランです。',
      links: [
        {{ url: 'https://travel.mk-group.co.jp/tourkyoto/furin-shojuin2026/', label: '🔔 ツアー詳細を見る' }}
      ]
    }},
    'maizuru': {{
      img: 'https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/20260620%20dr%20mishimura.jpg',
      title: '海とあじさいの絶景へ!! 舞鶴あじさい名所と絶景めぐり',
      date: '📷 2026年6月20日 ドライバー西村健撮影',
      desc: '海とあじさいが織りなす絶景。舞鶴のあじさい名所と絶景スポットを巡るツアーのひとコマです。',
      links: [
        {{ url: 'https://travel.mk-group.co.jp/tourkyoto/2026maizuruajisai/', label: '🌊 ツアー詳細を見る' }}
      ]
    }},
    'himatsuri': {{
      img: 'https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/21f355c5596cd370e7f58f9c99c3b246-600x400.webp',
      title: '鞍馬の火祭×くらま温泉 癒し旅',
      date: '📷 2025年10月22日 関係者撮影',
      desc: '年に一度、鞍馬の夜を燃やす伝統の火祭。巨大な松明が山里を照らす幻想的な夜をくらま温泉でゆっくり締めくくります。',
      links: [
        {{ url: 'https://travel.mk-group.co.jp/tourkyoto/himatsuri-stay/', label: '🏨 限定宿泊プランを見る' }},
        {{ url: 'https://travel.mk-group.co.jp/tourkyoto/himatsuri-1day/', label: '🔥 1dayプランを見る' }},
        {{ url: 'himatsuri2025.html', label: '📄 当日のレポートを見る' }}
      ]
    }}
  }};

  function openSeasonPopup(key) {{
    var d = SEASON_DATA[key];
    if (!d) return;
    document.getElementById('sp-img').src = d.img;
    document.getElementById('sp-title').textContent = d.title;
    var dateEl = document.getElementById('sp-date');
    if (d.date) {{ dateEl.textContent = d.date; dateEl.style.display = 'inline-block'; }}
    else {{ dateEl.style.display = 'none'; }}
    document.getElementById('sp-desc').textContent = d.desc;
    var btnWrap = document.getElementById('sp-btn-wrap');
    btnWrap.innerHTML = '';
    if (d.links) {{
      d.links.forEach(function(l) {{
        var a = document.createElement('a');
        a.href = l.url;
        a.textContent = l.label;
        a.target = '_blank';
        a.className = 'season-popup-btn';
        a.style.marginBottom = '6px';
        btnWrap.appendChild(a);
      }});
    }} else {{
      var a = document.createElement('a');
      a.href = d.url;
      a.textContent = d.label;
      a.target = '_blank';
      a.className = 'season-popup-btn';
      btnWrap.appendChild(a);
    }}
    document.getElementById('season-popup-overlay').classList.add('show');
  }}
  function closeSeasonPopup() {{
    document.getElementById('season-popup-overlay').classList.remove('show');
  }}

  function spTab(id, el) {{
    document.querySelectorAll('.sp-tab').forEach(function(t) {{ t.classList.remove('active'); }});
    document.querySelectorAll('.sp-panel').forEach(function(p) {{ p.classList.remove('active'); }});
    el.classList.add('active');
    var panel = document.getElementById('sp-' + id);
    if (panel) panel.classList.toggle('active');
  }}
  function closeSp() {{
    document.querySelectorAll('.sp-panel').forEach(function(p) {{ p.classList.remove('active'); }});
    document.querySelectorAll('.sp-tab').forEach(function(t) {{ t.classList.remove('active'); }});
  }}

  function toggleSection(el) {{
    var sub = el.nextElementSibling;
    var icon = el.querySelector('i');
    if (sub.style.display === 'none' || sub.style.display === '') {{
      sub.style.display = 'block';
      if (icon) icon.style.transform = 'rotate(180deg)';
    }} else {{
      sub.style.display = 'none';
      if (icon) icon.style.transform = '';
    }}
  }}

  function tourFilterStatus(status, el) {{
    var cards = document.querySelectorAll('.tour-card');
    var tabs = document.querySelectorAll('.ftab');
    var count = 0;
    tabs.forEach(function(t) {{ t.classList.remove('active'); }});
    if (el) el.classList.add('active');
    cards.forEach(function(c) {{
      var badge = c.querySelector('.sbadge');
      var badgeText = badge ? badge.textContent : '';
      var show = false;
      if (status === 'confirmed') show = badgeText.indexOf('催行確定') !== -1;
      else if (status === 'full') show = badgeText === '満席';
      else if (status === 'recruiting') show = badgeText === '募集中';
      if (show) {{ c.classList.remove('hidden'); count++; }}
      else {{ c.classList.add('hidden'); }}
    }});
    var note = document.getElementById('tour-count');
    if (note) note.textContent = count + '件のツアーを表示中';
  }}

  function scrollToArticle(id) {{
    var el = document.getElementById('article-' + id);
    if (!el) return;
    // モーダルで表示
    var content = el.cloneNode(true);
    content.style.display = 'block';
    content.style.border = 'none';
    content.style.padding = '0';
    content.style.marginBottom = '0';
    var modal = document.getElementById('article-modal-content');
    modal.innerHTML = '';
    modal.appendChild(content);
    document.getElementById('article-modal-overlay').classList.add('show');
    document.body.style.overflow = 'hidden';
  }}

  function closeArticleModal() {{
    document.getElementById('article-modal-overlay').classList.remove('show');
    document.body.style.overflow = '';
  }}

  function filterArticles(cat, el) {{
    var posts = document.querySelectorAll('.news-post');
    posts.forEach(function(p) {{
      if (cat === 'all' || p.getAttribute('data-category') === cat) {{
        p.style.display = 'block';
      }} else {{
        p.style.display = 'none';
      }}
    }});
  }}

  function toggleSeason(el) {{
    var body = el.nextElementSibling;
    var isOpen = el.classList.contains('open');
    el.classList.toggle('open', !isOpen);
    body.style.display = isOpen ? 'none' : 'block';
  }}

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

  // 正寿院（宇治田原）は木(3)金(4)土(5)日(0)のみ表示
  var SHOJUIN_WEEKDAYS = [0, 4, 5, 6]; // JS: 日=0,月=1,火=2,水=3,木=4,金=5,土=6
  function tourFilterByDate(dateKey) {{
    var parts = dateKey.split('-');
    var d = new Date(parseInt(parts[0]), parseInt(parts[1])-1, parseInt(parts[2]));
    var dow = d.getDay(); // 0=日,1=月,...,6=土
    var cards = document.querySelectorAll('#tours-grid .tour-card');
    var count = 0;
    cards.forEach(function(card) {{
      var datesAttr = card.getAttribute('data-dates') || '';
      var dates = datesAttr.split(',');
      var title = card.querySelector('.tour-title') ? card.querySelector('.tour-title').textContent : '';
      var isShojuin = title.indexOf('宇治田原') !== -1;
      // 随時催行（data-dates空）の場合
      if (datesAttr === '') {{
        // 正寿院は木金土日のみ
        if (isShojuin && SHOJUIN_WEEKDAYS.indexOf(dow) === -1) {{
          card.classList.add('hidden');
        }} else {{
          card.classList.remove('hidden'); count++;
        }}
      }} else if (dates.indexOf(dateKey) !== -1) {{
        card.classList.remove('hidden'); count++;
      }} else {{
        card.classList.add('hidden');
      }}
    }});
    document.querySelectorAll('.cd').forEach(function(c) {{
      c.classList.remove('selected');
      var paw = c.querySelector('.cd-paw');
      var num = c.querySelector('.cd-num');
      if (paw) paw.style.display = 'none';
      if (num) num.style.display = '';
    }});
    document.querySelectorAll('.cd').forEach(function(c) {{
      var parts = dateKey.split('-');
      var d = parts[2];
      var numEl = c.querySelector('.cd-num');
      if (numEl && numEl.textContent == String(parseInt(d)) &&
          (c.classList.contains('has-tour') || c.classList.contains('confirmed') ||
           c.classList.contains('full') || c.classList.contains('few'))) {{
        c.classList.add('selected');
        numEl.style.display = 'none';
        var paw = c.querySelector('.cd-paw');
        if (paw) paw.style.display = 'block';
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
    document.querySelectorAll('.cd').forEach(function(c) {{
      c.classList.remove('selected');
      var paw = c.querySelector('.cd-paw');
      var num = c.querySelector('.cd-num');
      if (paw) paw.style.display = 'none';
      if (num) num.style.display = '';
    }});
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
        c.innerHTML = '<span class="cd-num" style="display:block;text-align:center;">' + d + '</span><span class="cd-paw" style="display:none;text-align:center;">🐾</span><span style="display:block;text-align:right;font-size:9px;line-height:1;margin-top:-2px;">' + (t.em || '') + '</span>';
      }} else {{
        c.innerHTML = '<span class="cd-num">' + d + '</span><span class="cd-paw">🐾</span>';
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


def generate(data_path: Path, output_path: Path, articles_path: Path = None) -> None:
    """tour_data.json を読み込んでindex.htmlを生成"""
    with open(data_path, "r", encoding="utf-8") as f:
        tours = json.load(f)

    # 造成日記記事を読み込む
    articles_path = Path(data_path).parent / "articles.json"
    articles = []
    if articles_path.exists():
        with open(articles_path, "r", encoding="utf-8") as f:
            articles = json.load(f).get("articles", [])
        # 日付の新しい順に並べる
        articles.sort(key=lambda x: x.get("date", ""), reverse=True)
        # publish_atが設定されている場合は現在時刻と比較して非表示
        from datetime import datetime as _dt
        now = _dt.now()
        articles = [
            a for a in articles
            if not a.get("publish_at") or
            _dt.strptime(a["publish_at"], "%Y-%m-%d %H:%M") <= now
        ]

    updated_at = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    tour_js       = build_tour_js(tours)
    tour_cards    = build_tour_cards(tours)
    sidebar_status = build_sidebar_status(tours)

    # TOUR_REPORTSをJSオブジェクトに変換
    import json as _json
    tour_reports_js = _json.dumps(TOUR_REPORTS, ensure_ascii=False)

    # 造成日記記事HTMLを生成
    articles_html = ""
    new_count = sum(1 for a in articles if a.get("category") == "New！")
    # ナビ用：New！記事のタイトルリスト
    new_articles_nav = ""
    tamago_links = ""
    report_links = ""
    done_links = ""
    for art in articles:
        aid = art.get("id", "")
        title = art.get("title", "")
        cat = art.get("category", "")
        lnk = '<a href="#article-' + aid + '" style="padding-left:30px;font-size:10px;" onclick="scrollToArticle(\''+aid+'\')">' + title + '</a>'
        if cat == "New！":
            new_articles_nav += lnk
        elif cat == "企画のたまご":
            tamago_links += lnk
        elif cat == "レポート":
            report_links += lnk
        elif cat == "完成！":
            done_links += lnk
    for art in articles:
        cat = art.get("category", "")
        cat_color = {"New！": "#c0392b", "企画のたまご": "#e67e22", "レポート": "#2980b9", "完成！": "#27ae60"}.get(cat, "#8b7355")
        photos = art.get("photos", [])[:3]  # 最大3枚
        photos_html = ""
        if photos:
            cols = len(photos)
            imgs = "".join(f'<img src="{p}" alt="{art.get("title","")}">' for p in photos)
            photos_html = f'<div class="news-photos" style="grid-template-columns:repeat({cols},1fr);">{imgs}</div>'
        text_html = art.get("text", "").replace("\n", "<br>")
        aid = art.get("id", "")

        articles_html += f'''
      <div class="news-post" data-category="{cat}" id="article-{aid}">
        <div class="news-meta">
          <div class="nav-avatar">{art.get("author","?")[0]}</div>
          <div>
            <div class="news-author">{art.get("author","")}</div>
            <div class="news-dt">{art.get("date","")}</div>
          </div>
          <span style="margin-left:auto;font-size:10px;padding:2px 8px;border-radius:10px;background:{cat_color};color:#fff;">{cat}</span>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:13px;font-weight:500;color:#3c2e1e;margin-bottom:6px;">{art.get("title","")}</div>
          <div class="news-text">{text_html}</div>
          {photos_html}
        </div>
      </div>'''

    html = HTML_TEMPLATE.format(
        updated_at=updated_at,
        tour_js=tour_js,
        tour_cards=tour_cards,
        sidebar_status=sidebar_status,
        tour_reports_js=tour_reports_js,
        articles_html=articles_html,
        new_articles_nav=new_articles_nav,
        tamago_links=tamago_links,
        report_links=report_links,
        done_links=done_links,
        new_count=new_count,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html を生成しました: {output_path}")


def main():
    base = Path(__file__).parent
    data_path     = base / "tour_data.json"
    articles_path = base / "articles.json"
    output_path   = base / "index.html"

    if not data_path.exists():
        print(f"❌ {data_path} が見つかりません。先に scraper.py を実行してください。")
        sys.exit(1)

    generate(data_path, output_path, articles_path)


if __name__ == "__main__":
    main()
