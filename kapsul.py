
import datetime as dt
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from collections import Counter, defaultdict
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

APP_NAME = "Kapsul"

PHOTO_EXT = {
    ".jpg", ".jpeg", ".heic", ".heif", ".png", ".gif", ".bmp", ".tif", ".tiff",
    ".webp", ".dng", ".raw", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2",
}
VIDEO_EXT = {
    ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".3gp", ".mts", ".m2ts", ".wmv", ".mpg", ".mpeg",
}
BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]
# Urutan prioritas tag tanggal. CreationDate = tanggal video iPhone (lengkap dengan timezone).
DATE_TAGS = ["DateTimeOriginal", "CreationDate", "CreateDate", "MediaCreateDate"]
CHUNK = 200
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# --------------------------------------------------------------------------- #
# Logika inti
# --------------------------------------------------------------------------- #
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Folder data aplikasi (tempat exiftool disimpan setelah di-download)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def find_exiftool():
    names = ("exiftool.exe", "exiftool(-k).exe", "exiftool")
    for folder in (os.path.join(data_dir(), "exiftool"), app_dir()):
        for name in names:
            p = os.path.join(folder, name)
            if os.path.isfile(p):
                return p
    return shutil.which("exiftool")



def download_exiftool(progress):
    """Download dan instal ExifTool Windows 64-bit dari SourceForge."""

    import re

    headers = {
        "User-Agent": f"{APP_NAME}/1.0",
        "Accept": "application/octet-stream,*/*",
    }

    # Ambil versi terbaru dari server resmi ExifTool.
    version_urls = [
        "https://exiftool.sourceforge.net/ver.txt",
        "https://exiftool.org/ver.txt",
    ]

    ver = None
    errors = []

    for version_url in version_urls:
        try:
            req = urllib.request.Request(version_url, headers=headers)

            with urllib.request.urlopen(req, timeout=30) as response:
                candidate = response.read().decode("utf-8").strip()

            if re.fullmatch(r"\d+(?:\.\d+)*", candidate):
                ver = candidate
                break

        except Exception as e:
            errors.append(str(e))

    if not ver:
        raise RuntimeError(
            "Gagal mendapatkan versi ExifTool terbaru.\n"
            + "\n".join(errors)
        )

    # SourceForge merupakan sumber distribusi Windows ExifTool.
    urls = [
        f"https://sourceforge.net/projects/exiftool/files/"
        f"exiftool-{ver}_64.zip/download",

        f"https://exiftool.org/exiftool-{ver}_64.zip",
    ]

    work_dir = tempfile.mkdtemp(prefix="kapsul_exiftool_")
    zpath = os.path.join(work_dir, f"exiftool-{ver}_64.zip")
    extract_dir = os.path.join(work_dir, "extracted")

    try:
        os.makedirs(extract_dir)

        downloaded = False

        # Coba download dari sumber utama dan fallback.
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)

                with urllib.request.urlopen(req, timeout=120) as response:
                    total = int(response.headers.get("Content-Length") or 0)
                    got = 0

                    with open(zpath, "wb") as f:
                        while True:
                            block = response.read(65536)

                            if not block:
                                break

                            f.write(block)
                            got += len(block)

                            progress(
                                got // 1024,
                                (total or got) // 1024
                            )

                if not zipfile.is_zipfile(zpath):
                    raise RuntimeError(
                        "File download bukan ZIP ExifTool yang valid."
                    )

                downloaded = True
                break

            except Exception as e:
                errors.append(f"{url}: {e}")

                if os.path.exists(zpath):
                    os.remove(zpath)

        if not downloaded:
            raise RuntimeError(
                "Gagal mengunduh ExifTool.\n\n"
                + "\n".join(errors)
            )

        # Ekstrak ZIP dengan perlindungan path traversal.
        with zipfile.ZipFile(zpath, "r") as archive:
            for member in archive.infolist():
                target = os.path.abspath(
                    os.path.join(extract_dir, member.filename)
                )

                if os.path.commonpath(
                    [extract_dir, target]
                ) != os.path.abspath(extract_dir):
                    continue

                if member.is_dir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)

                    with archive.open(member) as src:
                        with open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)

        # Cari executable di dalam hasil ekstraksi.
        exe_source = None

        for root, dirs, files in os.walk(extract_dir):
            if "exiftool(-k).exe" in files:
                exe_source = os.path.join(
                    root, "exiftool(-k).exe"
                )
                break

            if "exiftool.exe" in files:
                exe_source = os.path.join(root, "exiftool.exe")
                break

        if not exe_source:
            raise RuntimeError(
                "exiftool.exe tidak ditemukan setelah ekstraksi."
            )

        # Salin seluruh isi folder agar exiftool_files ikut terpasang.
        source_dir = os.path.dirname(exe_source)
        dest = os.path.join(data_dir(), "exiftool")

        if os.path.isdir(dest):
            shutil.rmtree(dest)

        os.makedirs(os.path.dirname(dest), exist_ok=True)

        shutil.copytree(source_dir, dest)

        # Ubah nama executable untuk penggunaan command line.
        k = os.path.join(dest, "exiftool(-k).exe")
        e = os.path.join(dest, "exiftool.exe")

        if os.path.isfile(k):
            os.replace(k, e)

        if not os.path.isfile(e):
            raise RuntimeError("Instalasi exiftool.exe gagal.")

        # Pastikan executable benar-benar bisa dijalankan.
        result = subprocess.run(
            [e, "-ver"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=NO_WINDOW
        )

        if result.returncode != 0:
            raise RuntimeError(
                "ExifTool berhasil diekstrak tetapi gagal dijalankan.\n"
                + result.stderr
            )

        return e

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def norm(p):
    return os.path.normcase(os.path.normpath(p))


def parse_exif_date(value):
    """'2026:10:10 18:48:00(+07:00)' -> datetime, atau None kalau tidak valid."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        d = dt.datetime.strptime(value[:19].strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        try:
            d = dt.datetime.strptime(value[:10], "%Y:%m:%d")
        except ValueError:
            return None
    return d if d.year >= 1990 else None


def read_dates(exe, paths, stop, progress):
    """Baca tanggal metadata untuk semua file. Return {norm(path): datetime}."""
    result = {}
    for i in range(0, len(paths), CHUNK):
        if stop.is_set():
            break
        chunk = paths[i:i + CHUNK]
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8") as f:
            f.write("\n".join(chunk))
            argfile = f.name
        try:
            cmd = [exe, "-charset", "utf8", "-charset", "filename=utf8", "-json",
                   "-api", "largefilesupport=1"]
            cmd += [f"-{t}" for t in DATE_TAGS] + ["-@", argfile]
            proc = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
            data = json.loads(proc.stdout.decode("utf-8", "replace") or "[]")
        except Exception:
            data = []
        finally:
            try:
                os.remove(argfile)
            except OSError:
                pass
        for row in data:
            src = row.get("SourceFile")
            if not src:
                continue
            for tag in DATE_TAGS:
                d = parse_exif_date(row.get(tag))
                if d:
                    result[norm(src)] = d
                    break
        progress(min(i + CHUNK, len(paths)), len(paths))
    return result


def target_dir(root, item):
    sub = "Foto" if item["kind"] == "foto" else "Video"
    d = item["date"]
    if d is None:
        return os.path.join(root, "Tanpa Tanggal", sub)
    return os.path.join(root, str(d.year), f"{d.month:02d} {BULAN[d.month - 1]}", sub)


def unique_target(folder, name, size):
    """Return (path, status). status: 'ok' | 'duplikat' (nama & ukuran sama -> dilewati)."""
    base, ext = os.path.splitext(name)
    candidate = os.path.join(folder, name)
    n = 0
    while os.path.exists(candidate):
        if os.path.getsize(candidate) == size:
            return candidate, "duplikat"
        n += 1
        candidate = os.path.join(folder, f"{base}_{n}{ext}")
    return candidate, "ok"


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - Rapikan Foto & Video per Bulan")
        self.geometry("820x720")
        self.minsize(760, 640)

        self.exiftool = find_exiftool()
        self.q = queue.Queue()
        self.stop = threading.Event()
        self.plan = []          # hasil scan
        self.busy = False

        self.var_src = tk.StringVar()
        self.var_dst = tk.StringVar()
        self.var_same = tk.BooleanVar(value=True)
        self.var_mode = tk.StringVar(value="salin")
        self.var_sub = tk.BooleanVar(value=False)
        self.var_mod = tk.BooleanVar(value=True)

        self._build()
        self.after(100, self._poll)

        self.update_tool_status()
        if not self.exiftool:
            self.after(400, self.ask_download)

    # ---- tampilan ---------------------------------------------------------- #
    def _build(self):
        pad = {"padx": 10, "pady": 4}
        tool = ttk.LabelFrame(self, text="ExifTool (pembaca tanggal foto)")
        tool.pack(fill="x", **pad)
        self.lbl_tool = ttk.Label(tool, text="")
        self.lbl_tool.pack(side="left", padx=8, pady=6)
        self.btn_tool = ttk.Button(tool, text="Download ExifTool", command=self.start_download)
        self.btn_tool.pack(side="right", padx=8)
        self.btn_manual = ttk.Button(tool, text="Pilih manual...", command=self.pick_tool)
        self.btn_manual.pack(side="right")

        frm = ttk.LabelFrame(self, text="1. Pilih folder")
        frm.pack(fill="x", **pad)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Folder sumber:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frm, textvariable=self.var_src).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(frm, text="Pilih...", command=self.pick_src).grid(row=0, column=2, padx=8)

        ttk.Checkbutton(frm, text="Folder tujuan sama dengan folder sumber",
                        variable=self.var_same, command=self._toggle_dst
                        ).grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(frm, text="Folder tujuan:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.ent_dst = ttk.Entry(frm, textvariable=self.var_dst, state="disabled")
        self.ent_dst.grid(row=2, column=1, sticky="ew", padx=4)
        self.btn_dst = ttk.Button(frm, text="Pilih...", command=self.pick_dst, state="disabled")
        self.btn_dst.grid(row=2, column=2, padx=8)

        opt = ttk.LabelFrame(self, text="Opsi")
        opt.pack(fill="x", **pad)
        ttk.Radiobutton(opt, text="Salin (aman, file asli tetap ada)",
                        variable=self.var_mode, value="salin").grid(row=0, column=0, sticky="w", padx=8, pady=2)
        ttk.Radiobutton(opt, text="Pindahkan",
                        variable=self.var_mode, value="pindah").grid(row=0, column=1, sticky="w", padx=8)
        ttk.Checkbutton(opt, text="Sertakan sub-folder di dalam folder sumber",
                        variable=self.var_sub).grid(row=1, column=0, columnspan=2, sticky="w", padx=8)
        ttk.Checkbutton(opt, text="Kalau Date taken tidak ada, pakai tanggal Modified "
                                  "(jika dimatikan -> folder 'Tanpa Tanggal')",
                        variable=self.var_mod).grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

        act = ttk.Frame(self)
        act.pack(fill="x", **pad)
        self.btn_scan = ttk.Button(act, text="2. Scan Folder", command=self.start_scan)
        self.btn_scan.pack(side="left")
        self.btn_go = ttk.Button(act, text="3. Mulai Rapikan", command=self.start_run, state="disabled")
        self.btn_go.pack(side="left", padx=8)
        self.btn_stop = ttk.Button(act, text="Batal", command=self.stop.set, state="disabled")
        self.btn_stop.pack(side="left")

        self.lbl_sum = ttk.Label(self, text="Belum ada scan.", justify="left")
        self.lbl_sum.pack(fill="x", padx=12, pady=2)

        box = ttk.LabelFrame(self, text="Pratinjau hasil (jumlah file per folder bulan)")
        box.pack(fill="both", expand=True, **pad)
        cols = ("foto", "video")
        self.tree = ttk.Treeview(box, columns=cols, height=8)
        self.tree.heading("#0", text="Folder")
        self.tree.heading("foto", text="Foto")
        self.tree.heading("video", text="Video")
        self.tree.column("#0", width=380)
        self.tree.column("foto", width=90, anchor="e")
        self.tree.column("video", width=90, anchor="e")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.bar = ttk.Progressbar(self, mode="determinate")
        self.bar.pack(fill="x", padx=10, pady=(6, 2))
        self.lbl_prog = ttk.Label(self, text="")
        self.lbl_prog.pack(fill="x", padx=12)

        lg = ttk.LabelFrame(self, text="Log")
        lg.pack(fill="both", expand=True, **pad)
        self.txt = tk.Text(lg, height=7, wrap="word", state="disabled")
        sb2 = ttk.Scrollbar(lg, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb2.set)
        self.txt.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

    # ---- util GUI ---------------------------------------------------------- #
    def log(self, msg):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _toggle_dst(self):
        st = "disabled" if self.var_same.get() else "normal"
        self.ent_dst.configure(state=st)
        self.btn_dst.configure(state=st)
        self._reset_plan()

    def _reset_plan(self):
        self.plan = []
        self.btn_go.configure(state="disabled")

    def pick_src(self):
        p = filedialog.askdirectory(title="Pilih folder sumber (backup foto)")
        if p:
            self.var_src.set(os.path.normpath(p))
            self._reset_plan()

    def pick_dst(self):
        p = filedialog.askdirectory(title="Pilih folder tujuan")
        if p:
            self.var_dst.set(os.path.normpath(p))
            self._reset_plan()

    def dest_root(self):
        return self.var_src.get() if self.var_same.get() else self.var_dst.get()

    def set_busy(self, busy):
        self.busy = busy
        self.btn_scan.configure(state="disabled" if busy else "normal")
        self.btn_stop.configure(state="normal" if busy else "disabled")
        if busy:
            self.btn_go.configure(state="disabled")

    # ---- scan -------------------------------------------------------------- #
    # ---- exiftool ---------------------------------------------------------- #
    def update_tool_status(self):
        if self.exiftool:
            self.lbl_tool.configure(text="Siap digunakan")
            self.btn_tool.configure(text="Download ulang")
        else:
            self.lbl_tool.configure(text="Belum terpasang")
            self.btn_tool.configure(text="Download ExifTool")

    def ask_download(self):
        if self.busy or self.exiftool:
            return
        if messagebox.askyesno(
                APP_NAME,
                "ExifTool belum terpasang. Aplikasi memerlukannya untuk membaca tanggal "
                "foto dan video.\n\nDownload otomatis sekarang? (sekitar 10 MB, perlu internet)"):
            self.start_download()

    def _tool_buttons(self, state):
        self.btn_tool.configure(state=state)
        self.btn_manual.configure(state=state)

    def start_download(self):
        self.set_busy(True)
        self._tool_buttons("disabled")
        self.log("Mengunduh ExifTool dari exiftool.org ...")
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        try:
            path = download_exiftool(
                lambda g, t: self.q.put(("progress", g, t, "Mengunduh ExifTool (KB)")))
            self.q.put(("dl_done", path, None))
        except Exception as e:  # noqa: BLE001
            self.q.put(("dl_done", None, str(e)))

    def _download_done(self, path, err):
        self.set_busy(False)
        self._tool_buttons("normal")
        self.bar["value"] = 0
        self.lbl_prog.configure(text="")
        if path:
            self.exiftool = path
            self.log(f"ExifTool terpasang di: {path}")
        else:
            self.exiftool = find_exiftool()
            self.log(f"Download gagal: {err}")
            messagebox.showerror(
                APP_NAME,
                f"Download gagal:\n{err}\n\nCek koneksi internet, atau download manual dari "
                "exiftool.org (versi Windows 64-bit), ekstrak, lalu klik 'Pilih manual...'.")
        self.update_tool_status()

    def pick_tool(self):
        p = filedialog.askopenfilename(
            title="Pilih exiftool.exe (atau exiftool(-k).exe)",
            filetypes=[("exiftool", "*.exe"), ("Semua file", "*.*")])
        if not p:
            return
        dest = os.path.join(data_dir(), "exiftool")
        try:
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            shutil.copy2(p, os.path.join(dest, "exiftool.exe"))
            libs = os.path.join(os.path.dirname(p), "exiftool_files")
            if os.path.isdir(libs):
                shutil.copytree(libs, os.path.join(dest, "exiftool_files"))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"Gagal menyalin exiftool: {e}")
            return
        self.exiftool = find_exiftool()
        self.log(f"ExifTool dipasang dari: {p}")
        self.update_tool_status()

    # ---- scan -------------------------------------------------------------- #
    def start_scan(self):
        src = self.var_src.get().strip()
        if not self.exiftool:
            self.ask_download()
            return
        if not src or not os.path.isdir(src):
            messagebox.showerror(APP_NAME, "Pilih folder sumber dulu.")
            return
        if not self.var_same.get() and not self.var_dst.get().strip():
            messagebox.showerror(APP_NAME, "Pilih folder tujuan, atau centang 'sama dengan sumber'.")
            return
        self.stop.clear()
        self.set_busy(True)
        self.tree.delete(*self.tree.get_children())
        self.lbl_sum.configure(text="Sedang scan...")
        self.log(f"Scan: {src}")
        opts = (self.var_sub.get(), self.var_mod.get(), os.path.abspath(self.dest_root()))
        threading.Thread(target=self._scan_worker, args=(src, *opts), daemon=True).start()

    def _scan_worker(self, src, recursive, use_mod, dest_abs):
        q = self.q
        files, skipped = [], Counter()
        src_abs = os.path.abspath(src)
        for dirpath, dirnames, filenames in os.walk(src_abs):
            if not recursive:
                dirnames[:] = []
            elif dest_abs != src_abs:
                dirnames[:] = [d for d in dirnames if os.path.abspath(os.path.join(dirpath, d)) != dest_abs]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                full = os.path.join(dirpath, fn)
                if ext in PHOTO_EXT:
                    files.append({"path": full, "kind": "foto"})
                elif ext in VIDEO_EXT:
                    files.append({"path": full, "kind": "video"})
                else:
                    skipped[ext or "(tanpa ekstensi)"] += 1
            if self.stop.is_set():
                break

        q.put(("log", f"Ditemukan {len(files)} foto/video, {sum(skipped.values())} file format lain dilewati."))
        dates = read_dates(self.exiftool, [f["path"] for f in files], self.stop,
                           lambda i, n: q.put(("progress", i, n, "Membaca metadata")))
        for f in files:
            d = dates.get(norm(f["path"]))
            f["src"] = "metadata"
            if d is None:
                if use_mod:
                    try:
                        d = dt.datetime.fromtimestamp(os.path.getmtime(f["path"]))
                        f["src"] = "modified"
                    except OSError:
                        f["src"] = "tidak ada"
                else:
                    f["src"] = "tidak ada"
            f["date"] = d
        q.put(("scan_done", files, skipped, self.stop.is_set()))

    def _show_scan(self, files, skipped, cancelled):
        self.set_busy(False)
        self.bar["value"] = 0
        self.lbl_prog.configure(text="")
        if cancelled:
            self.lbl_sum.configure(text="Scan dibatalkan.")
            return
        self.plan = files
        n_foto = sum(1 for f in files if f["kind"] == "foto")
        n_vid = len(files) - n_foto
        n_meta = sum(1 for f in files if f["src"] == "metadata")
        n_mod = sum(1 for f in files if f["src"] == "modified")
        n_none = sum(1 for f in files if f["src"] == "tidak ada")
        other = ", ".join(f"{e} ({c})" for e, c in skipped.most_common(8)) or "-"
        self.lbl_sum.configure(text=(
            f"Foto: {n_foto}   |   Video: {n_vid}\n"
            f"Tanggal dari metadata: {n_meta}   |   dari Modified: {n_mod}   |   Tanpa tanggal: {n_none}\n"
            f"Format lain (dilewati): {other}"))

        groups = defaultdict(lambda: [0, 0])
        for f in files:
            d = f["date"]
            key = (d.year, d.month) if d else (0, 0)
            groups[key][0 if f["kind"] == "foto" else 1] += 1
        years = defaultdict(list)
        for (y, m), c in groups.items():
            years[y].append((m, c))
        for y in sorted(years, reverse=True):
            tf = sum(c[0] for _, c in years[y])
            tv = sum(c[1] for _, c in years[y])
            node = self.tree.insert("", "end", text=str(y) if y else "Tanpa Tanggal",
                                    values=(tf, tv), open=True)
            if y:
                for m, c in sorted(years[y]):
                    self.tree.insert(node, "end", text=f"{m:02d} {BULAN[m - 1]}", values=tuple(c))
        if files:
            self.btn_go.configure(state="normal")
            self.log("Scan selesai. Cek pratinjau, lalu klik 'Mulai Rapikan'.")
        else:
            self.log("Tidak ada foto/video yang cocok di folder itu.")

    # ---- eksekusi ---------------------------------------------------------- #
    def start_run(self):
        if not self.plan:
            return
        mode = self.var_mode.get()
        root = self.dest_root()
        if mode == "pindah" and not messagebox.askyesno(
                APP_NAME, "Mode PINDAH akan memindahkan file asli.\nLanjutkan?"):
            return
        if not messagebox.askyesno(APP_NAME, f"Proses {len(self.plan)} file ke:\n{root}\n\nMulai?"):
            return
        self.stop.clear()
        self.set_busy(True)
        threading.Thread(target=self._run_worker, args=(list(self.plan), root, mode), daemon=True).start()

    def _run_worker(self, plan, root, mode):
        q = self.q
        stats = Counter()
        lines = [f"{APP_NAME} - {dt.datetime.now():%Y-%m-%d %H:%M:%S} - mode {mode}"]
        total = len(plan)
        for i, item in enumerate(plan, 1):
            if self.stop.is_set():
                lines.append("DIBATALKAN oleh pengguna.")
                stats["dibatalkan"] = 1
                break
            src = item["path"]
            try:
                folder = target_dir(root, item)
                os.makedirs(folder, exist_ok=True)
                name = os.path.basename(src)
                if norm(os.path.dirname(src)) == norm(folder):
                    stats["sudah di tempat"] += 1
                else:
                    dest, status = unique_target(folder, name, os.path.getsize(src))
                    if status == "duplikat":
                        stats["duplikat dilewati"] += 1
                        lines.append(f"DUPLIKAT  {src}")
                    else:
                        (shutil.move if mode == "pindah" else shutil.copy2)(src, dest)
                        stats["berhasil"] += 1
                        lines.append(f"OK        {src} -> {dest}")
            except Exception as e:  # noqa: BLE001
                stats["gagal"] += 1
                lines.append(f"GAGAL     {src}: {e}")
                q.put(("log", f"Gagal: {os.path.basename(src)} ({e})"))
            if i % 10 == 0 or i == total:
                q.put(("progress", i, total, "Memproses"))
        try:
            with open(os.path.join(root, "Kapsul_log.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except OSError:
            pass
        q.put(("run_done", stats))

    # ---- antrean pesan dari thread ---------------------------------------- #
    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self.log(msg[1])
                elif kind == "progress":
                    _, i, n, label = msg
                    self.bar["maximum"] = max(n, 1)
                    self.bar["value"] = i
                    self.lbl_prog.configure(text=f"{label}: {i} / {n}")
                elif kind == "dl_done":
                    self._download_done(msg[1], msg[2])
                elif kind == "scan_done":
                    self._show_scan(*msg[1:])
                elif kind == "run_done":
                    self.set_busy(False)
                    s = msg[1]
                    txt = ", ".join(f"{k}: {v}" for k, v in s.items()) or "tidak ada yang diproses"
                    self.log(f"Selesai -> {txt}")
                    self.log("Detail tersimpan di Kapsul_log.txt (folder tujuan).")
                    messagebox.showinfo(APP_NAME, f"Selesai.\n\n{txt}")
                    self._reset_plan()
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    App().mainloop()