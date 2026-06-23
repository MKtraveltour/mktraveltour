"""
tour_editor.py  ―  旅とも手帳 ツアー管理ツール
タブ①：ツアー管理（tour_data.json）
タブ②：当日の様子レポート管理（tour_reports.json）
"""
import json
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOUR_DATA_PATH    = os.path.join(BASE_DIR, "tour_data.json")
TOUR_REPORTS_PATH = os.path.join(BASE_DIR, "tour_reports.json")
SCRAPER_PATH      = os.path.join(BASE_DIR, "scraper.py")
RUN_PATH          = os.path.join(BASE_DIR, "run.py")

TAGS_OPTIONS = ["event", "exp", "history", "flower", "summer", "autumn", "winter", "spring", "other"]
TAG_LABELS   = {
    "event":   "イベント・お祭り",
    "exp":     "体験・名所巡り",
    "history": "歴史・社寺巡り",
    "flower":  "季節の花",
    "summer":  "夏のツアー",
    "autumn":  "秋のツアー",
    "winter":  "冬のツアー",
    "spring":  "春のツアー",
    "other":   "その他",
}
SEASON_DATA_PATH = os.path.join(BASE_DIR, "season_data.json")

def load_season_data():
    if not os.path.exists(SEASON_DATA_PATH):
        return []
    with open(SEASON_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("seasons", [])

def save_season_data(seasons):
    with open(SEASON_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({"seasons": seasons}, f, ensure_ascii=False, indent=2)

ALWAYS_ON_KEYS = {"uma", "yokokuji_shuttle", "shojuin_sogei", "narihira_nishiyama", "momidiya"}

# ===== データ読み書き =====

def load_tours():
    if not os.path.exists(TOUR_DATA_PATH):
        return {}
    with open(TOUR_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tours(tours):
    with open(TOUR_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(tours, f, ensure_ascii=False, indent=2)

def load_reports():
    if not os.path.exists(TOUR_REPORTS_PATH):
        return {}
    with open(TOUR_REPORTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reports(reports):
    with open(TOUR_REPORTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)

# ===== メインアプリ =====

class TourEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("旅とも手帳 🗺 ツアー管理ツール")
        self.root.geometry("980x720")
        self.root.configure(bg="#faf8f5")
        self.tours   = load_tours()
        self.reports = load_reports()
        self.seasons = load_season_data()
        self._build_ui()

    def _build_ui(self):
        # ヘッダー
        hdr = tk.Frame(self.root, bg="#8b7355", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="旅とも手帳　ツアー管理ツール",
                 font=("", 15, "bold"), bg="#8b7355", fg="#fff").pack()

        # タブ
        style = ttk.Style()
        style.configure("TNotebook", background="#faf8f5", borderwidth=0)
        style.configure("TNotebook.Tab", font=("", 11, "bold"), padding=[16, 6])
        style.map("TNotebook.Tab", background=[("selected", "#8b7355")],
                  foreground=[("selected", "#fff")])

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=14, pady=10)

        # タブ①：ツアー管理
        tab1 = tk.Frame(nb, bg="#faf8f5")
        nb.add(tab1, text="🗺  ツアー管理")
        self._build_tour_tab(tab1)

        # タブ②：当日の様子レポート
        tab2 = tk.Frame(nb, bg="#faf8f5")
        nb.add(tab2, text="📸  当日の様子レポート")
        self._build_report_tab(tab2)

        # タブ③：季節・テーマ管理
        tab3 = tk.Frame(nb, bg="#faf8f5")
        nb.add(tab3, text="🌸  季節・テーマ")
        self._build_season_tab(tab3)

        # ステータスバー
        self.status_var = tk.StringVar(value="準備完了")
        tk.Label(self.root, textvariable=self.status_var, bg="#e0d8cc",
                 fg="#5c4a32", font=("", 9), anchor="w", padx=10).pack(fill="x", side="bottom")

    # ================================================================
    # タブ① ツアー管理
    # ================================================================

    def _build_tour_tab(self, parent):
        tk.Label(parent, text="催行日・催行状況はrun.py実行時に自動取得されます",
                 font=("", 9), bg="#faf8f5", fg="#e67e22").pack(anchor="w", padx=6, pady=(4,0))

        main = tk.Frame(parent, bg="#faf8f5")
        main.pack(fill="both", expand=True)

        # 左：一覧
        left = tk.LabelFrame(main, text=" ツアー一覧 ", bg="#faf8f5",
                              font=("", 10, "bold"), fg="#5c4a32", width=280)
        left.pack(side="left", fill="both", expand=False, padx=(0, 8))
        left.pack_propagate(False)

        flt = tk.Frame(left, bg="#faf8f5")
        flt.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(flt, text="表示:", bg="#faf8f5", font=("", 9)).pack(side="left")
        self.tour_filter_var = tk.StringVar(value="すべて")
        ttk.Combobox(flt, textvariable=self.tour_filter_var,
                     values=["すべて", "表示中", "非表示"],
                     state="readonly", width=8, font=("", 9)).pack(side="left", padx=4)
        self.tour_filter_var.trace_add("write", lambda *_: self._refresh_tour_list())

        self.tour_listbox = tk.Listbox(left, font=("", 9), selectbackground="#8b7355",
                                       selectforeground="#fff", activestyle="none",
                                       bg="#fff", bd=0, highlightthickness=1,
                                       highlightcolor="#c5b8a8")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tour_listbox.yview)
        self.tour_listbox.configure(yscrollcommand=sb.set)
        self.tour_listbox.pack(side="left", fill="both", expand=True, padx=(6,0), pady=4)
        sb.pack(side="left", fill="y", pady=4, padx=(0,4))
        self.tour_listbox.bind("<<ListboxSelect>>", self._on_tour_select)

        br = tk.Frame(left, bg="#faf8f5")
        br.pack(fill="x", padx=6, pady=(0,6))
        tk.Button(br, text="＋ 新規追加", command=self._new_tour,
                  bg="#8b7355", fg="#fff", font=("", 10, "bold"),
                  relief="flat", cursor="hand2").pack(fill="x", pady=(0,4))
        self.hide_btn = tk.Button(br, text="🙈 非表示にする", command=self._toggle_hidden,
                                  bg="#e67e22", fg="#fff", font=("", 10),
                                  relief="flat", cursor="hand2")
        self.hide_btn.pack(fill="x")

        # 右：編集フォーム
        right = tk.LabelFrame(main, text=" ツアー編集 ", bg="#faf8f5",
                               font=("", 10, "bold"), fg="#5c4a32")
        right.pack(side="left", fill="both", expand=True)

        def lbl(text):
            tk.Label(right, text=text, bg="#faf8f5", fg="#5c4a32",
                     font=("", 10)).pack(anchor="w", pady=(8,2), padx=4)

        r_key = tk.Frame(right, bg="#faf8f5")
        r_key.pack(fill="x", padx=4, pady=(8,0))
        tk.Label(r_key, text="キー（英数字・アンダーバー）", bg="#faf8f5",
                 fg="#5c4a32", font=("", 10)).pack(anchor="w")
        self.key_var = tk.StringVar()
        self.key_entry = tk.Entry(r_key, textvariable=self.key_var, font=("", 11),
                                  bg="#fff", relief="solid", bd=1)
        self.key_entry.pack(fill="x")

        lbl("ツアーURL")
        self.url_var = tk.StringVar()
        tk.Entry(right, textvariable=self.url_var, font=("", 10),
                 bg="#fff", relief="solid", bd=1).pack(fill="x", padx=4)

        lbl("タイトル（スクレイパーが自動取得）")
        self.title_var = tk.StringVar()
        tk.Entry(right, textvariable=self.title_var, font=("", 10),
                 bg="#f0f0f0", relief="solid", bd=1, state="readonly").pack(fill="x", padx=4)

        lbl("カテゴリタグ（複数選択可）")
        tag_frame = tk.Frame(right, bg="#faf8f5")
        tag_frame.pack(fill="x", padx=4)
        self.tag_vars = {}
        for i, tag in enumerate(TAGS_OPTIONS):
            v = tk.BooleanVar()
            self.tag_vars[tag] = v
            tk.Checkbutton(tag_frame, text=TAG_LABELS[tag], variable=v,
                           bg="#faf8f5", fg="#3c2e1e", font=("", 9),
                           selectcolor="#fff", activebackground="#faf8f5",
                           cursor="hand2").grid(row=i//4, column=i%4, sticky="w", padx=4, pady=1)

        self.always_on_var = tk.BooleanVar()
        tk.Checkbutton(right, text="随時催行ツアーとして登録",
                       variable=self.always_on_var, bg="#faf8f5", fg="#3c2e1e",
                       font=("", 10), selectcolor="#fff",
                       activebackground="#faf8f5", cursor="hand2").pack(anchor="w", padx=4, pady=(8,0))

        self.tour_status_label = tk.Label(right, text="", bg="#fdf5e8",
                                          fg="#8b4513", font=("", 10, "bold"),
                                          relief="flat", pady=4)
        self.tour_status_label.pack(fill="x", padx=4, pady=6)

        lbl("取得済み日程（参照のみ）")
        self.dates_text = tk.Text(right, height=3, font=("", 9),
                                  bg="#f8f8f8", relief="solid", bd=1,
                                  state="disabled", fg="#888")
        self.dates_text.pack(fill="x", padx=4)

        save_row = tk.Frame(right, bg="#faf8f5")
        save_row.pack(fill="x", padx=4, pady=10)
        tk.Button(save_row, text="💾  保存する", command=self._save_tour,
                  bg="#27ae60", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(
                      side="left", expand=True, fill="x", padx=(0,6))
        tk.Button(save_row, text="🚀  保存してHP更新", command=self._save_and_publish,
                  bg="#2980b9", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(
                      side="left", expand=True, fill="x")

        self._refresh_tour_list()

    # ================================================================
    # タブ② 当日の様子レポート
    # ================================================================

    def _build_report_tab(self, parent):
        main = tk.Frame(parent, bg="#faf8f5")
        main.pack(fill="both", expand=True)

        # 左：レポート一覧
        left = tk.LabelFrame(main, text=" レポート一覧 ", bg="#faf8f5",
                              font=("", 10, "bold"), fg="#5c4a32", width=260)
        left.pack(side="left", fill="both", expand=False, padx=(0,8))
        left.pack_propagate(False)

        self.report_listbox = tk.Listbox(left, font=("", 9), selectbackground="#8b7355",
                                         selectforeground="#fff", activestyle="none",
                                         bg="#fff", bd=0, highlightthickness=1,
                                         highlightcolor="#c5b8a8")
        sb2 = ttk.Scrollbar(left, orient="vertical", command=self.report_listbox.yview)
        self.report_listbox.configure(yscrollcommand=sb2.set)
        self.report_listbox.pack(side="left", fill="both", expand=True, padx=(6,0), pady=4)
        sb2.pack(side="left", fill="y", pady=4, padx=(0,4))
        self.report_listbox.bind("<<ListboxSelect>>", self._on_report_select)

        br2 = tk.Frame(left, bg="#faf8f5")
        br2.pack(fill="x", padx=6, pady=(0,6))
        tk.Button(br2, text="＋ 新規追加", command=self._new_report,
                  bg="#8b7355", fg="#fff", font=("", 10, "bold"),
                  relief="flat", cursor="hand2").pack(fill="x", pady=(0,4))
        tk.Button(br2, text="🗑 削除", command=self._delete_report,
                  bg="#c0392b", fg="#fff", font=("", 10),
                  relief="flat", cursor="hand2").pack(fill="x")

        # 右：編集フォーム
        right = tk.LabelFrame(main, text=" レポート編集 ", bg="#faf8f5",
                               font=("", 10, "bold"), fg="#5c4a32")
        right.pack(side="left", fill="both", expand=True)

        def lbl2(text):
            tk.Label(right, text=text, bg="#faf8f5", fg="#5c4a32",
                     font=("", 10)).pack(anchor="w", pady=(8,2), padx=4)

        # 日付（カレンダーキー）
        lbl2("催行日（カレンダーと紐づく日付）")
        date_row = tk.Frame(right, bg="#faf8f5")
        date_row.pack(fill="x", padx=4)
        self.report_date_var = tk.StringVar(value=str(date.today()))
        tk.Entry(date_row, textvariable=self.report_date_var, font=("", 11),
                 bg="#fff", relief="solid", bd=1, width=14).pack(side="left")
        tk.Label(date_row, text="形式: YYYY-MM-DD（例: 2025-10-22）",
                 bg="#faf8f5", fg="#aaa", font=("", 9)).pack(side="left", padx=8)

        # ツアータイトル
        lbl2("ツアー名")
        self.report_title_var = tk.StringVar()
        tk.Entry(right, textvariable=self.report_title_var, font=("", 11),
                 bg="#fff", relief="solid", bd=1).pack(fill="x", padx=4)

        # レポートページ
        lbl2("レポートページ（任意）")
        page_row = tk.Frame(right, bg="#faf8f5")
        page_row.pack(fill="x", padx=4)
        self.report_page_var = tk.StringVar()
        tk.Entry(page_row, textvariable=self.report_page_var, font=("", 10),
                 bg="#fff", relief="solid", bd=1).pack(side="left", fill="x", expand=True)
        tk.Label(page_row, text="例: himatsuri2025.html",
                 bg="#faf8f5", fg="#aaa", font=("", 9)).pack(side="left", padx=6)

        # 写真URL（3枚まで）
        lbl2("写真URL（1行1URL・最大3枚）")
        self.report_photo_box = scrolledtext.ScrolledText(
            right, font=("", 9), height=5, bg="#fff", relief="solid", bd=1, wrap="none")
        self.report_photo_box.pack(fill="x", padx=4)
        tk.Label(right,
                 text="💡 GitHubページのURLをそのまま貼ってもOK（github.com/blob/main/→自動変換）",
                 bg="#faf8f5", fg="#8b7355", font=("", 9)).pack(anchor="w", padx=4, pady=(2,0))

        # 保存ボタン
        save_row2 = tk.Frame(right, bg="#faf8f5")
        save_row2.pack(fill="x", padx=4, pady=10)
        tk.Button(save_row2, text="💾  保存する", command=self._save_report,
                  bg="#27ae60", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(
                      side="left", expand=True, fill="x", padx=(0,6))
        tk.Button(save_row2, text="🚀  保存してHP更新", command=self._save_report_and_publish,
                  bg="#2980b9", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(
                      side="left", expand=True, fill="x")

        self._refresh_report_list()

    # ================================================================
    # ツアー管理メソッド
    # ================================================================

    def _refresh_tour_list(self):
        flt = self.tour_filter_var.get()
        self.tour_listbox.delete(0, "end")
        self._tour_list_keys = []
        for key, tour in self.tours.items():
            hidden = tour.get("hidden", False)
            if flt == "表示中" and hidden: continue
            if flt == "非表示" and not hidden: continue
            icon = "🙈" if hidden else ("🔄" if key in ALWAYS_ON_KEYS else "✅")
            self.tour_listbox.insert("end", f"{icon} {tour.get('title', key)[:24]}")
            self._tour_list_keys.append(key)

    def _on_tour_select(self, event):
        sel = self.tour_listbox.curselection()
        if not sel: return
        key = self._tour_list_keys[sel[0]]
        self.selected_tour_key = key
        tour = self.tours[key]
        hidden = tour.get("hidden", False)
        self.key_var.set(key)
        self.key_entry.config(state="disabled")
        self.url_var.set(tour.get("url", ""))
        self.title_var.set(tour.get("title", ""))
        tags = tour.get("tags", [])
        for tag, var in self.tag_vars.items():
            var.set(tag in tags)
        self.always_on_var.set(key in ALWAYS_ON_KEYS)
        if hidden:
            self.tour_status_label.config(text="🙈 現在このツアーは非表示です", bg="#ffe0e0")
            self.hide_btn.config(text="👁 表示に戻す", bg="#27ae60")
        else:
            self.tour_status_label.config(text="✅ 現在このツアーは表示中です", bg="#e0ffe0")
            self.hide_btn.config(text="🙈 非表示にする", bg="#e67e22")
        dates = tour.get("dates", [])
        self.dates_text.config(state="normal")
        self.dates_text.delete("1.0", "end")
        self.dates_text.insert("1.0", "・".join(dates[:8]) + ("…" if len(dates) > 8 else ""))
        self.dates_text.config(state="disabled")

    def _new_tour(self):
        self.selected_tour_key = None
        self.key_var.set("")
        self.key_entry.config(state="normal")
        self.url_var.set("https://travel.mk-group.co.jp/tourkyoto/")
        self.title_var.set("（スクレイパーが自動取得します）")
        for v in self.tag_vars.values(): v.set(False)
        self.always_on_var.set(False)
        self.tour_status_label.config(text="新規ツアー追加モード", bg="#fdf5e8")
        self.hide_btn.config(text="🙈 非表示にする", bg="#e67e22")
        self.dates_text.config(state="normal")
        self.dates_text.delete("1.0", "end")
        self.dates_text.config(state="disabled")
        self.tour_listbox.selection_clear(0, "end")

    def _toggle_hidden(self):
        if not hasattr(self, 'selected_tour_key') or not self.selected_tour_key:
            messagebox.showwarning("未選択", "ツアーを選んでください"); return
        tour = self.tours[self.selected_tour_key]
        new_val = not tour.get("hidden", False)
        tour["hidden"] = new_val
        save_tours(self.tours)
        self._refresh_tour_list()
        label = "非表示" if new_val else "表示中"
        self.status_var.set(f"✅ 「{tour.get('title','')[:20]}」を{label}にしました")
        if new_val:
            self.tour_status_label.config(text="🙈 現在このツアーは非表示です", bg="#ffe0e0")
            self.hide_btn.config(text="👁 表示に戻す", bg="#27ae60")
        else:
            self.tour_status_label.config(text="✅ 現在このツアーは表示中です", bg="#e0ffe0")
            self.hide_btn.config(text="🙈 非表示にする", bg="#e67e22")

    def _save_tour(self):
        key = self.key_var.get().strip()
        url = self.url_var.get().strip()
        if not key:
            messagebox.showwarning("入力エラー", "キーを入力してください"); return
        if not url.startswith("http"):
            messagebox.showwarning("入力エラー", "URLを正しく入力してください"); return
        tags = [tag for tag, var in self.tag_vars.items() if var.get()]
        if hasattr(self, 'selected_tour_key') and self.selected_tour_key:
            self.tours[self.selected_tour_key]["url"]  = url
            self.tours[self.selected_tour_key]["tags"] = tags
            msg = f"「{self.tours[self.selected_tour_key].get('title', key)}」を更新しました"
        else:
            if key in self.tours:
                messagebox.showerror("重複エラー", f"キー「{key}」は既に存在します"); return
            self.tours[key] = {
                "key": key, "url": url,
                "title": "（次回run.py実行時に自動取得）",
                "image": "", "price": "", "dates": [], "statuses": [],
                "tags": tags, "updated_at": str(date.today()),
                "error": False, "hidden": False,
            }
            self._add_to_scraper(key, url)
            msg = f"新規ツアー「{key}」を追加しました"
        save_tours(self.tours)
        self._refresh_tour_list()
        self.status_var.set(f"✅ {msg}")
        messagebox.showinfo("保存完了", msg)

    def _add_to_scraper(self, key, url):
        if not os.path.exists(SCRAPER_PATH): return
        with open(SCRAPER_PATH, "r", encoding="utf-8") as f:
            src = f.read()
        import re
        insert_line = f'    "{key}": "{url}",\n'
        pattern = r'(TOUR_URLS\s*=\s*\{[^}]*?)(\n\})'
        match = re.search(pattern, src, re.DOTALL)
        if match and insert_line not in src:
            new_src = src[:match.end(1)] + "\n" + insert_line + src[match.end(1):]
            with open(SCRAPER_PATH, "w", encoding="utf-8") as f:
                f.write(new_src)

    # ================================================================
    # レポート管理メソッド
    # ================================================================

    def _refresh_report_list(self):
        self.report_listbox.delete(0, "end")
        self._report_keys = []
        for k in sorted(self.reports.keys(), reverse=True):
            r = self.reports[k]
            self.report_listbox.insert("end", f"📸 {k}  {r.get('title','')[:20]}")
            self._report_keys.append(k)

    def _on_report_select(self, event):
        sel = self.report_listbox.curselection()
        if not sel: return
        key = self._report_keys[sel[0]]
        self.selected_report_key = key
        r = self.reports[key]
        self.report_date_var.set(key)
        self.report_title_var.set(r.get("title", ""))
        self.report_page_var.set(r.get("page", ""))
        self.report_photo_box.delete("1.0", "end")
        self.report_photo_box.insert("1.0", "\n".join(r.get("photos", [])))

    def _new_report(self):
        self.selected_report_key = None
        self.report_date_var.set(str(date.today()))
        self.report_title_var.set("")
        self.report_page_var.set("")
        self.report_photo_box.delete("1.0", "end")
        self.report_listbox.selection_clear(0, "end")
        self.status_var.set("新規レポート追加モード")

    def _delete_report(self):
        if not hasattr(self, 'selected_report_key') or not self.selected_report_key:
            messagebox.showwarning("未選択", "削除するレポートを選んでください"); return
        key = self.selected_report_key
        title = self.reports[key].get("title", key)
        if not messagebox.askyesno("確認", f"「{title}」のレポートを削除しますか？"): return
        del self.reports[key]
        save_reports(self.reports)
        self.selected_report_key = None
        self._refresh_report_list()
        self._new_report()
        self.status_var.set(f"🗑 「{title}」を削除しました")

    def _fix_photo_url(self, u):
        return u.replace(
            "https://github.com/MKtraveltour/mktraveltour/blob/main/",
            "https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/"
        )

    def _save_report(self):
        dt   = self.report_date_var.get().strip()
        title = self.report_title_var.get().strip()
        page  = self.report_page_var.get().strip()
        photos = [self._fix_photo_url(p.strip())
                  for p in self.report_photo_box.get("1.0", "end").strip().splitlines()
                  if p.strip()][:3]  # 最大3枚

        if not dt or not title:
            messagebox.showwarning("入力エラー", "日付とツアー名を入力してください"); return
        # 日付形式チェック
        import re
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', dt):
            messagebox.showwarning("形式エラー", "日付はYYYY-MM-DD形式で入力してください\n例: 2025-10-22"); return

        self.reports[dt] = {"title": title, "page": page, "photos": photos}
        save_reports(self.reports)
        self.selected_report_key = dt
        self._refresh_report_list()
        self.status_var.set(f"✅ 「{title}」のレポートを保存しました")
        messagebox.showinfo("保存完了", f"「{title}」を保存しました\n\nカレンダーで {dt} をクリックすると写真が表示されます")

    def _save_report_and_publish(self):
        self._save_report()
        self._run_publish()

    def _save_and_publish(self):
        self._save_tour()
        self._run_publish()

    def _run_publish(self):
        self.status_var.set("🚀 HP更新中...")
        self.root.update()
        if not os.path.exists(RUN_PATH):
            messagebox.showerror("エラー", "run.pyが見つかりません"); return
        try:
            result = subprocess.run(
                ["python", RUN_PATH], cwd=BASE_DIR,
                capture_output=True, text=True, encoding="utf-8"
            )
            if result.returncode == 0:
                self.status_var.set("✅ HP更新完了！GitHubにpushしました")
                messagebox.showinfo("完了", "HP更新・GitHubへのpushが完了しました！")
            else:
                self.status_var.set("❌ エラーが発生しました")
                messagebox.showerror("エラー", result.stderr or result.stdout)
        except Exception as e:
            messagebox.showerror("エラー", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = TourEditor(root)
    root.mainloop()


    # ================================================================
    # タブ③ 季節・テーマ管理
    # ================================================================

    def _build_season_tab(self, parent):
        SEASON_OPTIONS = [
            ("spring", "🌸 春の京都"),
            ("summer", "☀️ 夏祭り"),
            ("autumn", "🍁 紅葉の秋"),
            ("winter", "❄️ 冬の情緒"),
        ]
        main = tk.Frame(parent, bg="#faf8f5")
        main.pack(fill="both", expand=True)

        # 左：一覧
        left = tk.LabelFrame(main, text=" 季節・テーマ一覧 ", bg="#faf8f5",
                              font=("", 10, "bold"), fg="#5c4a32", width=240)
        left.pack(side="left", fill="both", expand=False, padx=(0, 8))
        left.pack_propagate(False)

        self.season_listbox = tk.Listbox(left, font=("", 9), selectbackground="#8b7355",
                                          selectforeground="#fff", activestyle="none",
                                          bg="#fff", bd=0, highlightthickness=1,
                                          highlightcolor="#c5b8a8")
        sb3 = ttk.Scrollbar(left, orient="vertical", command=self.season_listbox.yview)
        self.season_listbox.configure(yscrollcommand=sb3.set)
        self.season_listbox.pack(side="left", fill="both", expand=True, padx=(6,0), pady=4)
        sb3.pack(side="left", fill="y", pady=4, padx=(0,4))
        self.season_listbox.bind("<<ListboxSelect>>", self._on_season_select)

        br3 = tk.Frame(left, bg="#faf8f5")
        br3.pack(fill="x", padx=6, pady=(0,6))
        tk.Button(br3, text="＋ 新規追加", command=self._new_season,
                  bg="#8b7355", fg="#fff", font=("", 10, "bold"),
                  relief="flat", cursor="hand2").pack(fill="x", pady=(0,4))
        tk.Button(br3, text="🗑 削除", command=self._delete_season,
                  bg="#c0392b", fg="#fff", font=("", 10),
                  relief="flat", cursor="hand2").pack(fill="x")

        # 右：編集フォーム
        right = tk.LabelFrame(main, text=" 編集 ", bg="#faf8f5",
                               font=("", 10, "bold"), fg="#5c4a32")
        right.pack(side="left", fill="both", expand=True)

        def lbl3(text):
            tk.Label(right, text=text, bg="#faf8f5", fg="#5c4a32",
                     font=("", 10)).pack(anchor="w", pady=(8,2), padx=4)

        # キー
        lbl3("キー（英数字・アンダーバー）")
        self.season_key_var = tk.StringVar()
        self.season_key_entry = tk.Entry(right, textvariable=self.season_key_var,
                                          font=("", 11), bg="#fff", relief="solid", bd=1)
        self.season_key_entry.pack(fill="x", padx=4)

        # 季節カテゴリ
        lbl3("季節カテゴリ")
        self.season_cat_var = tk.StringVar(value="summer")
        cat_frame = tk.Frame(right, bg="#faf8f5")
        cat_frame.pack(fill="x", padx=4)
        for val, lbl_text in SEASON_OPTIONS:
            tk.Radiobutton(cat_frame, text=lbl_text, value=val,
                           variable=self.season_cat_var,
                           bg="#faf8f5", font=("", 10), cursor="hand2",
                           activebackground="#faf8f5").pack(side="left", padx=4)

        # タイトル
        lbl3("タイトル（ポップアップに表示）")
        self.season_title_var = tk.StringVar()
        tk.Entry(right, textvariable=self.season_title_var, font=("", 11),
                 bg="#fff", relief="solid", bd=1).pack(fill="x", padx=4)

        # ナビラベル（絵文字+短い名前）
        lbl3("ナビ表示名（例: 🔥 鞍馬の火祭）")
        self.season_label_var = tk.StringVar()
        tk.Entry(right, textvariable=self.season_label_var, font=("", 11),
                 bg="#fff", relief="solid", bd=1).pack(fill="x", padx=4)

        # 写真URL
        lbl3("写真URL（GitHubのURLそのままでもOK）")
        self.season_img_var = tk.StringVar()
        tk.Entry(right, textvariable=self.season_img_var, font=("", 10),
                 bg="#fff", relief="solid", bd=1).pack(fill="x", padx=4)
        tk.Label(right, text="例: https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/ファイル名.jpg",
                 bg="#faf8f5", fg="#aaa", font=("", 8)).pack(anchor="w", padx=4)

        # 撮影日
        lbl3("撮影日（例: 📷 2025年10月22日 ドライバー撮影）")
        self.season_date_var = tk.StringVar()
        tk.Entry(right, textvariable=self.season_date_var, font=("", 10),
                 bg="#fff", relief="solid", bd=1).pack(fill="x", padx=4)

        # 説明文
        lbl3("説明文")
        self.season_desc_box = scrolledtext.ScrolledText(
            right, font=("", 10), height=3, bg="#fff", relief="solid", bd=1, wrap="word")
        self.season_desc_box.pack(fill="x", padx=4)

        # 関連リンク（最大3件）
        lbl3("関連リンク（1行につき「ラベル|URL」形式・最大3件）")
        self.season_links_box = scrolledtext.ScrolledText(
            right, font=("", 9), height=3, bg="#fff", relief="solid", bd=1, wrap="none")
        self.season_links_box.pack(fill="x", padx=4)
        tk.Label(right, text="例: 🔥 1dayプランを見る|https://travel.mk-group.co.jp/tourkyoto/himatsuri-1day/",
                 bg="#faf8f5", fg="#aaa", font=("", 8)).pack(anchor="w", padx=4)

        # 保存ボタン
        save_row3 = tk.Frame(right, bg="#faf8f5")
        save_row3.pack(fill="x", padx=4, pady=10)
        tk.Button(save_row3, text="💾  保存する", command=self._save_season,
                  bg="#27ae60", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(
                      side="left", expand=True, fill="x", padx=(0,6))
        tk.Button(save_row3, text="🚀  保存してHP更新", command=self._save_season_and_publish,
                  bg="#2980b9", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(
                      side="left", expand=True, fill="x")

        self._refresh_season_list()

    def _refresh_season_list(self):
        self.season_listbox.delete(0, "end")
        self._season_indices = list(range(len(self.seasons)))
        SEASON_ICON = {"spring":"🌸","summer":"☀️","autumn":"🍁","winter":"❄️"}
        for s in self.seasons:
            icon = SEASON_ICON.get(s.get("season",""), "📷")
            self.season_listbox.insert("end", f"{icon} {s.get('label', s.get('title',''))[:22]}")

    def _on_season_select(self, event):
        sel = self.season_listbox.curselection()
        if not sel: return
        self.selected_season_idx = sel[0]
        s = self.seasons[sel[0]]
        self.season_key_var.set(s.get("key",""))
        self.season_key_entry.config(state="disabled")
        self.season_cat_var.set(s.get("season","summer"))
        self.season_title_var.set(s.get("title",""))
        self.season_label_var.set(s.get("label",""))
        # 画像URL（raw変換）
        img = s.get("img","")
        self.season_img_var.set(img)
        self.season_date_var.set(s.get("date",""))
        self.season_desc_box.delete("1.0","end")
        self.season_desc_box.insert("1.0", s.get("desc",""))
        self.season_links_box.delete("1.0","end")
        links_text = "\n".join(f"{lk['label']}|{lk['url']}" for lk in s.get("links",[]))
        self.season_links_box.insert("1.0", links_text)

    def _new_season(self):
        self.selected_season_idx = None
        self.season_key_var.set("")
        self.season_key_entry.config(state="normal")
        self.season_cat_var.set("summer")
        self.season_title_var.set("")
        self.season_label_var.set("")
        self.season_img_var.set("https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/")
        self.season_date_var.set("")
        self.season_desc_box.delete("1.0","end")
        self.season_links_box.delete("1.0","end")
        self.season_listbox.selection_clear(0,"end")
        self.status_var.set("新規季節・テーマ追加モード")

    def _delete_season(self):
        if not hasattr(self,"selected_season_idx") or self.selected_season_idx is None:
            messagebox.showwarning("未選択","削除する項目を選んでください"); return
        label = self.seasons[self.selected_season_idx].get("label","")
        if not messagebox.askyesno("確認", f"「{label}」を削除しますか？"): return
        self.seasons.pop(self.selected_season_idx)
        save_season_data(self.seasons)
        self.selected_season_idx = None
        self._refresh_season_list()
        self._new_season()
        self.status_var.set(f"🗑 「{label}」を削除しました")

    def _fix_season_img_url(self, u):
        return u.replace(
            "https://github.com/MKtraveltour/mktraveltour/blob/main/",
            "https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/"
        )

    def _save_season(self):
        key   = self.season_key_var.get().strip()
        title = self.season_title_var.get().strip()
        label = self.season_label_var.get().strip()
        img   = self._fix_season_img_url(self.season_img_var.get().strip())
        dt    = self.season_date_var.get().strip()
        desc  = self.season_desc_box.get("1.0","end").strip()
        cat   = self.season_cat_var.get()

        # リンク解析
        links = []
        for line in self.season_links_box.get("1.0","end").strip().splitlines():
            if "|" in line:
                lbl, url = line.split("|", 1)
                links.append({"label": lbl.strip(), "url": url.strip()})

        if not key or not title:
            messagebox.showwarning("入力エラー","キーとタイトルを入力してください"); return

        new_item = {
            "key": key, "season": cat, "label": label or title,
            "thumb_title": label or title,
            "img": img, "title": title, "date": dt, "desc": desc, "links": links
        }

        if hasattr(self,"selected_season_idx") and self.selected_season_idx is not None:
            self.seasons[self.selected_season_idx] = new_item
            msg = f"「{label}」を更新しました"
        else:
            # キー重複チェック
            if any(s["key"] == key for s in self.seasons):
                messagebox.showerror("重複エラー", f"キー「{key}」は既に存在します"); return
            self.seasons.append(new_item)
            msg = f"「{label}」を追加しました"

        save_season_data(self.seasons)
        self._refresh_season_list()
        self.status_var.set(f"✅ {msg}")
        messagebox.showinfo("保存完了", msg)

    def _save_season_and_publish(self):
        self._save_season()
        self._run_publish()
