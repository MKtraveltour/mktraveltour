# MKトラベル HP 自動更新システム セットアップ手順

## ファイル構成

サーバーの任意のフォルダ（例: C:\mktravel\）に以下のファイルを配置してください：

```
C:\mktravel\
├── scraper.py            # ① MKトラベル公式サイトからデータ取得
├── generate_hp_auto.py   # ② tour_data.json → index.html を生成
├── update.bat            # ③ ①②をまとめて実行するバッチ
├── mktravel_schedule.xml # ④ タスクスケジューラ登録用XML
├── tour_data.json        # ⑤ 取得データの一時保存（自動生成）
├── index.html            # ⑥ 生成されるHP（自動生成）
└── update_log.txt        # ⑦ 実行ログ（自動生成）
```

---

## 手順1：Pythonと必要ライブラリのインストール

コマンドプロンプトを管理者権限で開いて実行：

```
pip install requests beautifulsoup4
```

---

## 手順2：フォルダパスの変更

`update.bat` と `mktravel_schedule.xml` の中の
**C:\mktravel\** を実際のフォルダパスに書き換えてください。

---

## 手順3：動作テスト

コマンドプロンプトで実際のフォルダに移動して実行：

```
cd C:\mktravel
update.bat
```

`tour_data.json` と `index.html` が生成されれば成功です。

---

## 手順4：タスクスケジューラへの登録

コマンドプロンプト（管理者権限）で実行：

```
schtasks /create /xml "C:\mktravel\mktravel_schedule.xml" /tn "MKトラベルHP自動更新"
```

確認コマンド：
```
schtasks /query /tn "MKトラベルHP自動更新"
```

---

## 手順5：実行スケジュールの確認

デフォルトでは **毎日 朝6時と正午の2回** 実行されます。
変更したい場合は `mktravel_schedule.xml` の `<StartBoundary>` を編集してから
再登録してください。

---

## 新しいツアーを追加するには

`scraper.py` の `TOUR_URLS` 辞書にURLを追加するだけです：

```python
TOUR_URLS = {
    "ajisai_harf":    "https://travel.mk-group.co.jp/tourkyoto/2026ajisai-harf/",
    "ayabe_ajisai":   "https://travel.mk-group.co.jp/tourkyoto/ayabe-ajisai2026/",
    "rousoku":        "https://travel.mk-group.co.jp/tourkyoto/rousokumatsuri2026/",
    "himatsuri_stay": "https://travel.mk-group.co.jp/tourkyoto/himatsuri-stay/",
    # ↓ 新しいツアーを追加
    "new_tour": "https://travel.mk-group.co.jp/tourkyoto/新しいURL/",
}
```

追加後に `update.bat` を実行すれば自動で反映されます。

---

## トラブルシューティング

| 症状 | 確認事項 |
|------|----------|
| スクレイピングに失敗 | ネットワーク接続・MKトラベルサイトへのアクセス可否を確認 |
| index.htmlが更新されない | `update_log.txt` でエラー内容を確認 |
| タスクが実行されない | タスクスケジューラの「最後の実行結果」を確認 |
| 料金・日程が取れない | MKトラベルのサイト構造が変わった可能性あり。scraper.pyの抽出ロジックを見直す |
