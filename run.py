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

now = datetime.now().strftime("%Y-%m-%d %H:%M")
# ネットワークドライブ対応: packファイルのリネームエラーを防ぐ設定
os.system('git config gc.auto 0')          # 自動GC無効（packリネームが起きない）
os.system('git config pack.windowMemory 0') # packメモリ制限
os.system('git add -A')  # 新規生成HTMLも含めすべての変更を追加
os.system(f'git commit -m "auto update {now}"')
os.system('git pull origin main --no-edit')  # pushの前に必ずpull
os.system('git push --no-thin origin main')  # --no-thin でpackリネームを抑制

print("\n✅ すべての処理が完了しました！")
