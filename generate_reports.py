"""
generate_reports.py
tour_reports.jsonの各レポートからHTMLページを自動生成する
"""
import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
REPORTS_PATH = BASE_DIR / "tour_reports.json"

def key_to_filename(date_key: str) -> str:
    return "report_" + date_key.replace("-", "") + ".html"

def generate_report_html(date_key: str, report: dict) -> str:
    title     = report.get("title", "")
    photos    = report.get("photos", [])
    desc      = report.get("desc", "")
    hero      = report.get("hero", photos[0] if photos else "")
    catch     = report.get("catch", "")
    shot_date = report.get("shot_date", "")
    audio     = report.get("audio", "")
    audio_label = report.get("audio_label", "自然の音")

    # 催行年
    try:
        year_str = f"{datetime.strptime(date_key, '%Y-%m-%d').year}年開催"
    except:
        year_str = ""

    # ヘッダー撮影日表示
    shot_date_html = ""
    if shot_date:
        shot_date_html = f'<div class="hero-date">📅 {shot_date}</div>'

    # 煽り文句
    catch_html = ""
    if catch:
        catch_html = f'<div class="hero-catch">{catch}</div>'

    # 説明文HTML（写真の上）
    desc_html = ""
    if desc:
        import re as _re
        # 空行（\n\n以上）で段落分割、単純な改行は<br>に変換
        para_blocks = _re.split(r'\n{2,}', desc)
        paragraphs = "".join(
            f'<p>{block.strip().replace(chr(10), "<br>")}</p>'
            for block in para_blocks if block.strip()
        )
        desc_html = f'<div class="report-desc">{paragraphs}</div>'

    # 写真（音声あり→スライドショー、なし→グリッド）
    photos_html = ""
    if photos and audio:
        audio_url = f"https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/{audio}"
        slides_js = json.dumps(photos, ensure_ascii=False)
        photos_html = f'''<div class="slideshow-wrap">
  <div class="slideshow-inner" id="ss-inner">
    {"".join(f'<div class="ss-slide{" active" if i==0 else ""}" style="background-image:url({json.dumps(p)})"></div>' for i,p in enumerate(photos))}
    <div class="ss-overlay"></div>
    <div class="ss-controls">
      <span class="ss-label" id="ss-label">🎵 {audio_label}</span>
      <button class="ss-btn" id="ss-mute" onclick="ssMute()"><i class="ti ti-volume"></i></button>
      <button class="ss-btn" id="ss-pause" onclick="ssPause()"><i class="ti ti-player-pause"></i></button>
    </div>
    <div class="ss-dots" id="ss-dots"></div>
    <div class="ss-progress"><div class="ss-bar" id="ss-bar"></div></div>
  </div>
  <audio id="ss-audio" src="{audio_url}" loop autoplay></audio>
</div>
<style>
.slideshow-wrap{{margin-bottom:24px;border-radius:12px;overflow:hidden;}}
.slideshow-inner{{position:relative;height:340px;background:#111;}}
.ss-slide{{position:absolute;inset:0;opacity:0;transition:opacity 2s ease;background-size:cover;background-position:center;}}
.ss-slide.active{{opacity:1;}}
.ss-overlay{{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,0.05),rgba(0,0,0,0.4));}}
.ss-controls{{position:absolute;top:12px;right:12px;display:flex;align-items:center;gap:8px;}}
.ss-label{{font-size:11px;color:rgba(255,255,255,0.85);background:rgba(0,0,0,0.35);padding:4px 10px;border-radius:20px;}}
.ss-btn{{background:rgba(255,255,255,0.18);border:none;color:#fff;width:34px;height:34px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:15px;}}
.ss-btn:hover{{background:rgba(255,255,255,0.32);}}
.ss-dots{{position:absolute;bottom:22px;left:50%;transform:translateX(-50%);display:flex;gap:6px;}}
.ss-dot{{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,0.4);cursor:pointer;transition:background 0.3s;}}
.ss-dot.active{{background:#fff;}}
.ss-progress{{position:absolute;bottom:0;left:0;right:0;height:2px;background:rgba(255,255,255,0.2);}}
.ss-bar{{height:100%;background:rgba(255,255,255,0.7);transition:width 0.1s linear;}}
@media(max-width:600px){{.slideshow-inner{{height:240px;}}}}
</style>
<script>
(function(){{
  var PHOTOS={slides_js};
  var cur=0,paused=false,muted=false,prog=0,iv;
  var INTERVAL=5000;
  var slides=document.querySelectorAll('.ss-slide');
  var dotsEl=document.getElementById('ss-dots');
  var audio=document.getElementById('ss-audio');
  audio.volume=0.6;
  PHOTOS.forEach(function(_,i){{
    var d=document.createElement('div');d.className='ss-dot'+(i===0?' active':'');
    d.onclick=function(){{goTo(i);}};dotsEl.appendChild(d);
  }});
  function goTo(idx){{
    slides[cur].classList.remove('active');
    dotsEl.children[cur].classList.remove('active');
    cur=idx;prog=0;
    slides[cur].classList.add('active');
    dotsEl.children[cur].classList.add('active');
  }}
  iv=setInterval(function(){{
    if(paused)return;
    prog+=100/(INTERVAL/100);
    if(prog>=100){{goTo((cur+1)%PHOTOS.length);return;}}
    document.getElementById('ss-bar').style.width=prog+'%';
  }},100);
  window.ssPause=function(){{
    paused=!paused;
    document.getElementById('ss-pause').innerHTML=paused?'<i class="ti ti-player-play"></i>':'<i class="ti ti-player-pause"></i>';
    paused?audio.pause():audio.play();
  }};
  window.ssMute=function(){{
    muted=!muted;audio.muted=muted;
    document.getElementById('ss-mute').innerHTML=muted?'<i class="ti ti-volume-off"></i>':'<i class="ti ti-volume"></i>';
    document.getElementById('ss-label').style.opacity=muted?'0.4':'1';
  }};
}})();
</script>'''
    elif photos:
        items = []
        for idx, p in enumerate(photos):
            items.append(
                f'<div class="photo-item" onclick="openViewer({idx})" style="cursor:pointer;">'
                f'<img src="{p}" alt="{title}"></div>'
            )
        photos_html = f'<div class="photo-grid">{"".join(items)}</div>'

    # 写真データをJSに埋め込む
    photos_js = json.dumps(photos, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | 旅とも手帳</title>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-C523Q39L5Q"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-C523Q39L5Q');
  </script>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Noto Sans JP', sans-serif; background: #f5f0e8; color: #3c2e1e; }}
    a {{ text-decoration: none; color: inherit; }}

    /* ヒーローヘッダー */
    .hero {{
      position: relative;
      height: 280px;
      overflow: hidden;
      background: #1a1a1a;
    }}
    .hero-img {{
      position: absolute; inset: 0;
      width: 100%; height: 100%;
      object-fit: cover; object-position: center;
      opacity: 0.65;
    }}
    .hero-overlay {{
      position: absolute; inset: 0;
      background: linear-gradient(to bottom, rgba(0,0,0,0.2), rgba(0,0,0,0.6));
    }}
    .hero-body {{
      position: relative; z-index: 1;
      height: 100%;
      display: flex; flex-direction: column;
      justify-content: flex-end;
      padding: 24px 20px;
      color: #fff;
    }}
    .hero-year {{
      font-size: 11px;
      background: rgba(255,255,255,0.25);
      border-radius: 4px;
      padding: 2px 8px;
      display: inline-block;
      margin-bottom: 8px;
      backdrop-filter: blur(4px);
    }}
    .hero-catch {{
      font-size: 13px;
      font-weight: 400;
      color: rgba(255,255,255,0.85);
      margin-bottom: 4px;
    }}
    .hero-title {{
      font-size: 20px;
      font-weight: 700;
      line-height: 1.4;
      margin-bottom: 8px;
      text-shadow: 0 1px 4px rgba(0,0,0,0.5);
    }}
    .hero-date {{
      font-size: 12px;
      color: rgba(255,255,255,0.8);
      background: rgba(255,255,255,0.12);
      backdrop-filter: blur(4px);
      border-radius: 4px;
      padding: 3px 10px;
      display: inline-block;
    }}

    /* メインコンテンツ */
    .wrap {{
      max-width: 860px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }}
    .section-title {{
      font-size: 14px;
      font-weight: 500;
      color: #5c4a32;
      border-left: 4px solid #8b7355;
      padding-left: 10px;
      margin-bottom: 14px;
    }}

    /* 説明文 */
    .report-desc {{
      background: #fff;
      border-radius: 10px;
      padding: 16px 20px;
      margin-bottom: 20px;
      border: 1px solid #e0d8cc;
      font-size: 13px;
      line-height: 1.85;
      color: #5c4a32;
    }}
    .report-desc p {{ margin-bottom: 8px; }}
    .report-desc p:last-child {{ margin-bottom: 0; }}

    /* 写真グリッド */
    .photo-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      margin-bottom: 24px;
    }}
    .photo-item img {{
      width: 100%;
      aspect-ratio: 4/3;
      object-fit: cover;
      border-radius: 6px;
      display: block;
      transition: opacity 0.2s;
    }}
    .photo-item:hover img {{ opacity: 0.9; }}

    /* 戻るボタン */
    .back-btn {{
      display: block;
      text-align: center;
      background: #8b7355;
      color: #fff;
      border-radius: 8px;
      padding: 14px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.2s;
    }}
    .back-btn:hover {{ background: #7a6448; }}

    /* ビューワー */
    .viewer-overlay {{
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.92); z-index: 9999;
      align-items: center; justify-content: center; flex-direction: column;
    }}
    .viewer-overlay.show {{ display: flex; }}
    .viewer-img {{
      max-width: 90vw; max-height: 72vh;
      object-fit: contain; border-radius: 8px; display: block;
    }}
    .viewer-caption {{
      color: rgba(255,255,255,0.8); font-size: 12px;
      margin-top: 10px; text-align: center;
    }}
    .viewer-nav {{
      display: flex; align-items: center; gap: 24px; margin-top: 14px;
    }}
    .vn-btn {{
      background: rgba(255,255,255,0.15); border: none; color: #fff;
      font-size: 26px; width: 48px; height: 48px; border-radius: 50%;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: background 0.2s;
    }}
    .vn-btn:hover {{ background: rgba(255,255,255,0.3); }}
    .vn-btn:disabled {{ opacity: 0.25; cursor: default; }}
    .vn-counter {{ color: rgba(255,255,255,0.6); font-size: 12px; min-width: 48px; text-align: center; }}
    .viewer-close {{
      position: absolute; top: 16px; right: 20px;
      color: #fff; font-size: 26px; cursor: pointer;
      background: none; border: none; line-height: 1;
    }}
    @media (max-width: 600px) {{
      .hero {{ height: 220px; }}
      .hero-title {{ font-size: 16px; }}
      .photo-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>

  <!-- ポップアップビューワー -->
  <div class="viewer-overlay" id="viewer-overlay" onclick="onOverlayClick(event)">
    <button class="viewer-close" onclick="closeViewer()">✕</button>
    <img class="viewer-img" id="viewer-img" src="" alt="">
    <div class="viewer-caption" id="viewer-caption"></div>
    <div class="viewer-nav">
      <button class="vn-btn" id="vn-prev" onclick="viewerMove(-1)">&#8249;</button>
      <span class="vn-counter" id="vn-counter"></span>
      <button class="vn-btn" id="vn-next" onclick="viewerMove(1)">&#8250;</button>
    </div>
  </div>

  <!-- ヒーローヘッダー -->
  <div class="hero">
    {f'<img class="hero-img" src="{hero}" alt="{title}">' if hero else ''}
    <div class="hero-overlay"></div>
    <div class="hero-body">
      {f'<div class="hero-year">{year_str}</div>' if year_str else ''}
      {catch_html}
      <div class="hero-title">{title}</div>
      {shot_date_html}
    </div>
  </div>

  <!-- メインコンテンツ -->
  <div class="wrap">
    {desc_html}
    {f'<div class="section-title">当日の様子</div>' if photos else ''}
    {photos_html}
    <a href="index.html" class="back-btn">← MKトラベル手帳に戻る</a>
  </div>

<script>
  var PHOTOS = {photos_js};
  var _vIdx = 0;

  function openViewer(idx) {{
    _vIdx = idx;
    _updateViewer();
    document.getElementById('viewer-overlay').classList.add('show');
    document.body.style.overflow = 'hidden';
  }}

  function _updateViewer() {{
    document.getElementById('viewer-img').src = PHOTOS[_vIdx];
    document.getElementById('viewer-caption').textContent = (_vIdx + 1) + ' / ' + PHOTOS.length;
    document.getElementById('vn-prev').disabled = (_vIdx === 0);
    document.getElementById('vn-next').disabled = (_vIdx === PHOTOS.length - 1);
  }}

  function viewerMove(delta) {{
    _vIdx = Math.max(0, Math.min(PHOTOS.length - 1, _vIdx + delta));
    _updateViewer();
  }}

  function closeViewer() {{
    document.getElementById('viewer-overlay').classList.remove('show');
    document.body.style.overflow = '';
  }}

  function onOverlayClick(e) {{
    if (e.target === document.getElementById('viewer-overlay')) closeViewer();
  }}

  document.addEventListener('keydown', function(e) {{
    if (!document.getElementById('viewer-overlay').classList.contains('show')) return;
    if (e.key === 'ArrowLeft')  viewerMove(-1);
    if (e.key === 'ArrowRight') viewerMove(1);
    if (e.key === 'Escape')     closeViewer();
  }});
</script>
</body>
</html>'''

def generate_all_reports():
    if not REPORTS_PATH.exists():
        print("  tour_reports.json が見つかりません")
        return

    with open(REPORTS_PATH, "r", encoding="utf-8") as f:
        reports = json.load(f)

    updated = False
    for date_key, report in reports.items():
        if not report.get("page"):
            report["page"] = key_to_filename(date_key)
            updated = True

        # .html拡張子がなければ自動補完
        page = report["page"]
        if page and not page.endswith(".html"):
            page = page + ".html"
            report["page"] = page
            updated = True
        out_path = BASE_DIR / page
        html = generate_report_html(date_key, report)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  📄 {page} を生成しました")

    if updated:
        with open(REPORTS_PATH, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        print("  💾 tour_reports.json を更新しました")

if __name__ == "__main__":
    generate_all_reports()
