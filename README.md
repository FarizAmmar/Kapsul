# Kapsul

**Organize your photos and videos effortlessly.**

Kapsul adalah aplikasi desktop Windows yang membantu merapikan koleksi foto dan video secara otomatis berdasarkan tahun dan bulan pengambilan gambar.

Dengan memanfaatkan metadata tanggal menggunakan ExifTool, Kapsul dapat mengelompokkan file ke dalam struktur folder yang terorganisir tanpa perlu mengatur file satu per satu.

## ✨ Features

- **Automatic Organization** — Mengelompokkan foto dan video berdasarkan tahun dan bulan.
- **Metadata-Based Date Detection** — Membaca tanggal asli dari metadata foto dan video.
- **iPhone Video Support** — Mendukung pembacaan `CreationDate`, termasuk metadata video iPhone.
- **Multiple File Formats** — Mendukung berbagai format foto dan video.
- **Copy & Move Modes** — Pilih untuk menyalin atau memindahkan file.
- **Recursive Scanning** — Memindai subfolder secara opsional.
- **Duplicate Detection** — Mendeteksi file duplikat berdasarkan nama dan ukuran.
- **Preview Before Processing** — Melihat estimasi jumlah file sebelum diproses.
- **Progress Tracking** — Memantau proses scanning dan pengorganisasian.
- **Operation Log** — Menyimpan detail proses ke `Kapsul_log.txt`.
- **Automatic ExifTool Installation** — Mengunduh dan memasang ExifTool secara otomatis jika belum tersedia.

## 🖥️ Supported Platforms

| Requirement      | Support                                  |
| ---------------- | ---------------------------------------- |
| Operating System | Windows                                  |
| Architecture     | 64-bit Windows ExifTool                  |
| Python           | Python 3                                 |
| GUI Framework    | Tkinter                                  |
| Metadata Engine  | ExifTool                                 |
| Internet         | Required for automatic ExifTool download |

## 📸 Supported File Formats

### Images

`.jpg`, `.jpeg`, `.heic`, `.heif`, `.png`, `.gif`, `.bmp`, `.tif`, `.tiff`, `.webp`, `.dng`, `.raw`, `.cr2`, `.cr3`, `.nef`, `.arw`, `.orf`, `.rw2`

### Videos

`.mov`, `.mp4`, `.m4v`, `.avi`, `.mkv`, `.3gp`, `.mts`, `.m2ts`, `.wmv`, `.mpg`, `.mpeg`

## 📂 How Files Are Organized

Kapsul automatically creates folders based on the date associated with each file.

Example output:

```text
Photos/
│
├── 2024/
│   ├── 01 Januari/
│   │   ├── Foto/
│   │   └── Video/
│   │
│   ├── 02 Februari/
│   │   ├── Foto/
│   │   └── Video/
│
├── 2025/
│   ├── 01 Januari/
│   │   ├── Foto/
│   │   └── Video/
│
├── 2026/
│   ├── 10 Oktober/
│   │   ├── Foto/
│   │   └── Video/
│
├── Tanpa Tanggal/
│   ├── Foto/
│   └── Video/
│
└── Kapsul_log.txt
```

Files without a valid date will be placed in `Tanpa Tanggal` if the modified-date fallback is disabled or unavailable.

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
```

Navigate to the project directory:

```bash
cd Kapsul
```

### 2. Check Python Installation

Make sure Python 3 is installed.

```bash
python --version
```

Or on Windows:

```bash
py --version
```

### 3. Run the Application

Kapsul uses Python's built-in libraries, including Tkinter. No additional Python packages are required by the application source.

Run:

```bash
py kapsul.py
```

Replace `kapsul.py` with the actual Python filename if it is different.

### 4. Install ExifTool

On the first launch, Kapsul checks whether ExifTool is available.

If ExifTool is not installed, the application will offer to download it automatically.

Requirements:

- Internet connection.
- Windows 64-bit ExifTool.
- Sufficient disk space.

ExifTool will be stored in:

```text
%LOCALAPPDATA%\Kapsul\exiftool\
```

You can also install ExifTool manually through the application's **Pilih manual...** option.

## ⚙️ Usage

1. Open Kapsul.
2. Select the source folder containing your photos and videos.
3. Choose whether the destination folder should be the same as the source folder.
4. Select the organization mode:
   - **Salin** — Copy files while keeping the originals.
   - **Pindahkan** — Move files to the destination.
5. Configure additional options:
   - Include subfolders.
   - Use the file's modified date if the metadata date is unavailable.
6. Click **Scan Folder**.
7. Review the scanning results and folder preview.
8. Click **Mulai Rapikan**.
9. Wait until the process finishes.

A detailed operation log will be saved as:

```text
Kapsul_log.txt
```

inside the destination folder.

## 🛠️ Development

If you want to modify or develop Kapsul, follow these instructions.

### Run in Development Mode

```bash
py kapsul.py
```

### Build Executable (.exe)

You can package Kapsul into a standalone Windows executable using PyInstaller.

Install PyInstaller:

```bash
py -m pip install pyinstaller
```

Build the application:

```bash
py -m PyInstaller --onefile --windowed --name Kapsul kapsul.py
```

The generated executable will be available in:

```text
dist/Kapsul.exe
```

To build again from a clean state:

```bash
py -m PyInstaller --clean --onefile --windowed --name Kapsul kapsul.py
```

**Note:** The generated executable still needs access to ExifTool. Kapsul can download and install it automatically on first launch.

## 🧠 Date Detection Priority

Kapsul uses the following metadata tags in order:

1. `DateTimeOriginal`
2. `CreationDate`
3. `CreateDate`
4. `MediaCreateDate`

If no valid metadata date is found, Kapsul can optionally use the file's modified date.

If neither date is available, the file is categorized under `Tanpa Tanggal`.

Dates earlier than 1990 are considered invalid.

## 🔒 Data Safety

Kapsul is designed to organize files locally on your computer.

- No cloud upload is required for organizing files.
- Copy mode keeps the original files intact.
- Move mode transfers the original files to the destination.
- Duplicate detection helps avoid copying files with the same name and size.
- A confirmation dialog appears before moving files or starting the operation.

**Recommendation:** Always keep a backup of important photos and videos before using Move mode.

## 🐛 Troubleshooting

### ExifTool is not installed

Make sure you have an internet connection and try downloading ExifTool through the application.

Alternatively, download ExifTool manually and use the **Pilih manual...** button.

### Failed to download ExifTool

Check your internet connection and try again.

You can also install ExifTool manually from:

https://exiftool.org/

### Files are placed in Tanpa Tanggal

The file may not contain a supported date metadata tag.

Enable the modified-date fallback option if you want Kapsul to use the file's last modified date.

### Some files are skipped

Kapsul only processes the supported image and video extensions listed in this documentation.

## 📄 License

Choose and specify your preferred open-source license before distributing this project.

For example: MIT License.

---

**Kapsul — Keep your memories organized.**
