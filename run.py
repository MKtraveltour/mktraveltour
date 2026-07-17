"""
run.py - 旅とも手帳 一括更新スクリプト
1. 翌年URL自動チェック（hidden:Trueのツアー）
2. スクレイピング（tour_data.json更新）
3. HP生成（index.html生成）
4. GitHub push
"""
import subprocess
import sys
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run(cmd, desc):
    print(f"\n{'='*50}")
    print(f"▶ {desc}")
    print('='*50)
    result = subprocess.run(cmd, cwd=BASE_DIR, shell=True)
    if result.returncode != 0:
        print(f"❌ エラーが発生しました: {desc}")
        sys.exit(1)

# --- 必要ライブラリの確認 ---
try:
    import requests
except ImportError:
    print("📦 requestsをインストール中...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)

try:
    import bs4
except ImportError:
    print("📦 beautifulsoup4をインストール中...")
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4"], check=True)

# --- STEP 1: 翌年URL自動チェック ---
print("\n🔍 STEP 1: 非表示ツアーの翌年URL自動チェック")
from check_next_year_url import check_and_update
check_and_update()

# --- STEP 2: スクレイピング ---
run(f'"{sys.executable}" scraper.py', "STEP 2: ツアー情報スクレイピング")

# --- STEP 3: HP生成 ---
run(f'"{sys.executable}" generate_hp_auto.py', "STEP 3: index.html生成")

# --- STEP 3.5: レポートページ自動生成 ---
print(f"\n{'='*50}")
print("▶ STEP 3.5: レポートページ自動生成")
print('='*50)
from generate_reports import generate_all_reports
generate_all_reports()

# --- STEP 4: GitHub push ---
print(f"\n{'='*50}")
print("▶ STEP 4: GitHub push")
print('='*50)

import glob, time

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# ネットワークドライブ対応: すべての自動メンテナンスを無効化
os.system('git config gc.auto 0')
os.system('git config gc.autoDetach false')
os.system('git config gc.cruftPacks false')
os.system('git config pack.windowMemory 0')
os.system('git config pack.depth 0')
os.system('git config pack.window 0')
os.system('git config core.multiPackIndex false')      # multi-pack-index無効
os.system('git config fetch.writeCommitGraph false')   # commitGraph書き込み無効
os.system('git config maintenance.auto false')         # 自動メンテナンス完全無効
os.system('git config maintenance.strategy none')

# pushの前に残留tmpファイルを削除
pack_dir = os.path.join(BASE_DIR, '.git', 'objects', 'pack')
for tmp_file in glob.glob(os.path.join(pack_dir, '.tmp-*')):
    try:
        os.remove(tmp_file)
        print(f"🗑️ 残留tmpファイル削除: {os.path.basename(tmp_file)}")
    except Exception as e:
        print(f"⚠️ tmp削除スキップ: {e}")

os.system('git add -A')
os.system(f'git commit -m "auto update {now}"')
os.system('git pull origin main --no-edit')

# push（失敗時は最大3回リトライ）
print("📤 GitHub pushを開始...")
for attempt in range(1, 4):
    ret = subprocess.run(
        'git push --no-thin origin main',
        shell=True, cwd=BASE_DIR
    ).returncode
    if ret == 0:
        print("✅ Push成功")
        break
    print(f"⚠️ Push失敗（{attempt}/3回目）。3秒後に再試行...")
    time.sleep(3)
    for tmp_file in glob.glob(os.path.join(pack_dir, '.tmp-*')):
        try: os.remove(tmp_file)
        except: pass
else:
    print("❌ Pushが3回失敗しました。")
    sys.exit(1)

print("\n✅ すべての処理が完了しました！")
