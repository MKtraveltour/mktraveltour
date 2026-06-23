import json
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import date

ARTICLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles.json")
CATEGORIES = ["New！", "企画のたまご", "レポート", "完成！"]

# ===== データ読み書き =====

def load_articles():
    if not os.path.exists(ARTICLES_PATH):
        return []
    with open(ARTICLES_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("articles", [])

def save_articles(articles):
    with open(ARTICLES_PATH, "w", encoding="utf-8") as f:
        json.dump({"articles": articles}, f, ensure_ascii=False, indent=2)

def next_id(articles):
    nums = []
    for a in articles:
        try:
            nums.append(int(a["id"]))
        except:
            pass
    return str(max(nums) + 1).zfill(3) if nums else "001"

# ===== メインアプリ =====

class ArticleEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("旅とも手帳 ✏️ 記事管理ツール")
        self.root.geometry("900x680")
        self.root.configure(bg="#faf8f5")
        self.articles = load_articles()
        self.selected_index = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        # ---- 上部タイトル ----
        header = tk.Frame(self.root, bg="#8b7355", pady=10)
        header.pack(fill="x")
        tk.Label(header, text="旅とも手帳　記事管理ツール", font=("", 15, "bold"),
                 bg="#8b7355", fg="#fff").pack()

        # ---- メイン2カラム ----
        main = tk.Frame(self.root, bg="#faf8f5")
        main.pack(fill="both", expand=True, padx=16, pady=12)

        # 左：記事一覧
        left = tk.LabelFrame(main, text=" 記事一覧 ", bg="#faf8f5",
                              font=("", 10, "bold"), fg="#5c4a32")
        left.pack(side="left", fill="both", expand=False, padx=(0,10))
        left.configure(width=260)
        left.pack_propagate(False)

        # 一覧ボックス
        self.listbox = tk.Listbox(left, font=("", 10), selectbackground="#8b7355",
                                  selectforeground="#fff", activestyle="none",
                                  bg="#fff", bd=0, highlightthickness=1,
                                  highlightcolor="#c5b8a8")
        self.listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        # 一覧下ボタン
        btn_row = tk.Frame(left, bg="#faf8f5")
        btn_row.pack(fill="x", padx=6, pady=(0,6))
        tk.Button(btn_row, text="＋ 新規", command=self._new_article,
                  bg="#8b7355", fg="#fff", font=("", 10, "bold"),
                  relief="flat", cursor="hand2", padx=8).pack(side="left", expand=True, fill="x", padx=(0,4))
        tk.Button(btn_row, text="🗑 削除", command=self._delete_article,
                  bg="#c0392b", fg="#fff", font=("", 10),
                  relief="flat", cursor="hand2", padx=8).pack(side="left", expand=True, fill="x")

        # 右：編集フォーム
        right = tk.LabelFrame(main, text=" 記事編集 ", bg="#faf8f5",
                               font=("", 10, "bold"), fg="#5c4a32")
        right.pack(side="left", fill="both", expand=True)

        def lbl(parent, text):
            tk.Label(parent, text=text, bg="#faf8f5", fg="#5c4a32",
                     font=("", 10)).pack(anchor="w", pady=(8,2))

        lbl(right, "タイトル")
        self.title_var = tk.StringVar()
        tk.Entry(right, textvariable=self.title_var, font=("", 11),
                 bg="#fff", relief="solid", bd=1).pack(fill="x", padx=4)

        row2 = tk.Frame(right, bg="#faf8f5")
        row2.pack(fill="x", padx=4, pady=(8,0))

        f_author = tk.Frame(row2, bg="#faf8f5")
        f_author.pack(side="left", fill="x", expand=True, padx=(0,8))
        tk.Label(f_author, text="著者", bg="#faf8f5", fg="#5c4a32", font=("",10)).pack(anchor="w")
        self.author_var = tk.StringVar()
        tk.Entry(f_author, textvariable=self.author_var, font=("", 11),
                 bg="#fff", relief="solid", bd=1).pack(fill="x")

        f_cat = tk.Frame(row2, bg="#faf8f5")
        f_cat.pack(side="left", fill="x", expand=True, padx=(0,8))
        tk.Label(f_cat, text="カテゴリ", bg="#faf8f5", fg="#5c4a32", font=("",10)).pack(anchor="w")
        self.cat_var = tk.StringVar(value=CATEGORIES[0])
        ttk.Combobox(f_cat, textvariable=self.cat_var, values=CATEGORIES,
                     state="readonly", font=("",11), width=14).pack(fill="x")

        f_date = tk.Frame(row2, bg="#faf8f5")
        f_date.pack(side="left", fill="x", expand=True)
        tk.Label(f_date, text="日付", bg="#faf8f5", fg="#5c4a32", font=("",10)).pack(anchor="w")
        self.date_var = tk.StringVar(value=str(date.today()))
        tk.Entry(f_date, textvariable=self.date_var, font=("", 11),
                 bg="#fff", relief="solid", bd=1).pack(fill="x")

        lbl(right, "本文（改行はそのままEnterでOK）")
        self.text_box = scrolledtext.ScrolledText(right, font=("", 10), height=10,
                                                  bg="#fff", relief="solid", bd=1,
                                                  wrap="word")
        self.text_box.pack(fill="both", expand=True, padx=4)

        lbl(right, "写真URL（1行1URL）")
        self.photo_box = scrolledtext.ScrolledText(right, font=("", 9), height=3,
                                                   bg="#fff", relief="solid", bd=1,
                                                   wrap="none")
        self.photo_box.pack(fill="x", padx=4)

        # 予約投稿
        pub_frame = tk.Frame(right, bg="#fdf5e8", relief="solid", bd=1)
        pub_frame.pack(fill="x", padx=4, pady=(10,0))
        pub_inner = tk.Frame(pub_frame, bg="#fdf5e8", pady=6, padx=8)
        pub_inner.pack(fill="x")
        self.use_publish_var = tk.BooleanVar()
        tk.Checkbutton(pub_inner, text="⏰ 予約投稿する",
                       variable=self.use_publish_var,
                       command=self._toggle_publish,
                       bg="#fdf5e8", fg="#8b4513", font=("", 10, "bold"),
                       selectcolor="#fff", activebackground="#fdf5e8",
                       cursor="hand2").pack(side="left")
        self.publish_var = tk.StringVar(value="")
        self.publish_entry = tk.Entry(pub_inner, textvariable=self.publish_var,
                                      font=("", 10), bg="#fff", relief="solid", bd=1,
                                      width=18, state="disabled")
        self.publish_entry.pack(side="left", padx=(10,4))
        tk.Label(pub_inner, text="例: 2026-07-01 09:00",
                 bg="#fdf5e8", fg="#aaa", font=("", 9)).pack(side="left")

        # 保存ボタン
        save_row = tk.Frame(right, bg="#faf8f5")
        save_row.pack(fill="x", padx=4, pady=10)
        tk.Button(save_row, text="💾  保存する", command=self._save_article,
                  bg="#27ae60", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(side="left", expand=True, fill="x", padx=(0,8))
        tk.Button(save_row, text="🚀  保存してHP更新", command=self._save_and_publish,
                  bg="#2980b9", fg="#fff", font=("", 12, "bold"),
                  relief="flat", cursor="hand2", pady=6).pack(side="left", expand=True, fill="x")

        # ---- ステータスバー ----
        self.status_var = tk.StringVar(value="準備完了")
        tk.Label(self.root, textvariable=self.status_var, bg="#e0d8cc",
                 fg="#5c4a32", font=("", 9), anchor="w", padx=10).pack(fill="x", side="bottom")

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for a in self.articles:
            cat = a.get("category", "")
            badge = {"New！":"🆕", "企画のたまご":"🥚", "レポート":"📋", "完成！":"✅"}.get(cat, "📝")
            self.listbox.insert("end", f"{badge} {a['date']}  {a['title']}")

    def _on_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.selected_index = sel[0]
        a = self.articles[self.selected_index]
        self.title_var.set(a.get("title", ""))
        self.author_var.set(a.get("author", ""))
        self.cat_var.set(a.get("category", CATEGORIES[0]))
        self.date_var.set(a.get("date", str(date.today())))
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", a.get("text", ""))
        self.photo_box.delete("1.0", "end")
        self.photo_box.insert("1.0", "\n".join(a.get("photos", [])))
        # 予約投稿
        pa = a.get("publish_at", "")
        if pa:
            self.use_publish_var.set(True)
            self.publish_var.set(pa)
            self.publish_entry.config(state="normal")
        else:
            self.use_publish_var.set(False)
            self.publish_var.set("")
            self.publish_entry.config(state="disabled")

    def _toggle_publish(self):
        if self.use_publish_var.get():
            self.publish_entry.config(state="normal")
            if not self.publish_var.get():
                # デフォルトで明日の9:00をセット
                from datetime import timedelta
                tomorrow = date.today() + timedelta(days=1)
                self.publish_var.set(f"{tomorrow} 09:00")
        else:
            self.publish_entry.config(state="disabled")

    def _new_article(self):
        self.selected_index = None
        self.title_var.set("")
        self.author_var.set("")
        self.cat_var.set(CATEGORIES[0])
        self.date_var.set(str(date.today()))
        self.text_box.delete("1.0", "end")
        self.photo_box.delete("1.0", "end")
        self.use_publish_var.set(False)
        self.publish_var.set("")
        self.publish_entry.config(state="disabled")
        self.listbox.selection_clear(0, "end")
        self.status_var.set("新規記事モード")

    def _get_form(self):
        def fix_url(u):
            # github.com/blob/main/ → raw.githubusercontent.com/main/ に自動変換
            u = u.replace(
                "https://github.com/MKtraveltour/mktraveltour/blob/main/",
                "https://raw.githubusercontent.com/MKtraveltour/mktraveltour/main/"
            )
            return u
        photos = [fix_url(p.strip()) for p in self.photo_box.get("1.0", "end").strip().splitlines() if p.strip()]
        publish_at = self.publish_var.get().strip() if self.use_publish_var.get() else ""
        return {
            "title":      self.title_var.get().strip(),
            "author":     self.author_var.get().strip(),
            "category":   self.cat_var.get(),
            "date":       self.date_var.get().strip(),
            "text":       self.text_box.get("1.0", "end").rstrip("\n"),
            "photos":     photos,
            "publish_at": publish_at,
        }

    def _save_article(self):
        form = self._get_form()
        if not form["title"]:
            messagebox.showwarning("入力エラー", "タイトルを入力してください")
            return
        if self.selected_index is not None:
            # 既存記事を更新
            self.articles[self.selected_index].update(form)
            msg = f"「{form['title']}」を更新しました"
        else:
            # 新規追加（先頭に挿入）
            new_article = {"id": next_id(self.articles)}
            new_article.update(form)
            self.articles.insert(0, new_article)
            self.selected_index = 0
            msg = f"「{form['title']}」を追加しました"
        save_articles(self.articles)
        self._refresh_list()
        self.listbox.selection_set(self.selected_index)
        self.status_var.set(f"✅ {msg}")
        messagebox.showinfo("保存完了", msg)

    def _delete_article(self):
        if self.selected_index is None:
            messagebox.showwarning("未選択", "削除する記事を選んでください")
            return
        title = self.articles[self.selected_index].get("title", "")
        if not messagebox.askyesno("確認", f"「{title}」を削除しますか？"):
            return
        self.articles.pop(self.selected_index)
        save_articles(self.articles)
        self.selected_index = None
        self._refresh_list()
        self._new_article()
        self.status_var.set(f"🗑 「{title}」を削除しました")

    def _save_and_publish(self):
        self._save_article()
        self.status_var.set("🚀 HP更新中...")
        self.root.update()
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")
        if not os.path.exists(script):
            messagebox.showerror("エラー", "run.pyが見つかりません")
            return
        try:
            result = subprocess.run(
                ["python", script],
                cwd=os.path.dirname(script),
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
    app = ArticleEditor(root)
    root.mainloop()
