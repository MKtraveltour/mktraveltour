# -*- coding: utf-8 -*-
import subprocess
import sys
import os
from datetime import datetime

def install_requirements():
    required = ["requests", "beautifulsoup4", "lxml"]
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_").replace("beautifulsoup4", "bs4"))
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)

install_requirements()

FOLDER = r"Z:\mktravel"

def run_cmd(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd or FOLDER, capture_output=True, text=True, encoding="utf-8")
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

def log(msg):
    with open(os.path.join(FOLDER, "update_log.txt"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {msg}\n")
    print(msg)

def main():
    os.chdir(FOLDER)
    print(f"=== 自動更新開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print("\n[1/3] ツアー情報を取得中...")
    r1 = subprocess.run([sys.executable, "scraper.py"], cwd=FOLDER)
    if r1.returncode != 0:
        log("scraping failed")
        return 1
    print("\n[2/3] index.html を生成中...")
    r2 = subprocess.run([sys.executable, "generate_hp_auto.py"], cwd=FOLDER)
    if r2.returncode != 0:
        log("html generation failed")
        return 1
    print("\n[3/3] GitHubにアップロード中...")
    run_cmd(["git", "pull", "origin", "main", "--rebase"])
    run_cmd(["git", "add", "index.html", "tour_data.json", "generate_hp_auto.py", "scraper.py", "articles.json"])
    run_cmd(["git", "commit", "-m", f"auto update {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    ret = run_cmd(["git", "push", "origin", "main"])
    if ret != 0:
        log("git push failed")
        return 1
    log("success")
    return 0

if __name__ == "__main__":
    sys.exit(main())