# AI Face Attendance System

> **A complete, production-ready desktop attendance management system powered by AI face recognition.**

---

## Features

- 🎯 **Real-time face recognition** using InsightFace (ArcFace / buffalo_sc model)
- 📷 **Live webcam feed** with annotated bounding boxes and employee names
- 🗄️ **SQLite persistence** — all data stored in `data/attendance.db`
- 🔐 **Secure admin panel** with bcrypt password hashing and login lockout
- 👤 **Employee registration** with multi-sample face capture
- 📅 **Attendance records** with search, filters, and pagination
- 📤 **CSV & Excel export** with flexible date and employee filters
- ⚙️ **Settings** for threshold, cooldown, camera index, and password management

---

## Technology Stack

| Component | Library |
|---|---|
| Face detection | OpenCV DNN (Caffe SSD) |
| Face recognition | InsightFace (ArcFace/buffalo_sc) |
| Camera | OpenCV |
| UI | CustomTkinter |
| Database | SQLite 3 (via `sqlite3` std-lib) |
| Security | bcrypt |
| Reports | Pandas + openpyxl |

---

## Prerequisites

- Windows 10 / 11 (x64)
- Python 3.11 or 3.13
- Webcam (built-in or USB)
- Internet connection on first launch (to download the InsightFace buffalo_sc model, ~200 MB)
- Disk space: ~1 GB (model + dependencies)

---

## Installation

```bat
:: 1. Clone or copy the project
cd AI_Face_Attendance

:: 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

:: 3. Upgrade pip
python -m pip install --upgrade pip

:: 4. Install dependencies
pip install -r requirements.txt

:: 5. Run the application
python main.py
```

> **First launch**: InsightFace will automatically download the `buffalo_sc` model (~200 MB) to  
> `C:\Users\<you>\.insightface\models\buffalo_sc\`. An internet connection is required only the first time.

---

## First-Time Admin Setup

1. Launch `python main.py`.
2. Click **Admin Login** on the scanner screen.
3. Because no admin account exists yet, the setup form appears.
4. Enter a username (≥ 3 characters) and password (≥ 8 characters).
5. Click **Create Admin Account**.
6. Log in with your new credentials.

---

## Running the Application

```bat
python main.py
```

The live scanner starts automatically:

- Detected faces are highlighted with bounding boxes.
- Green box = recognized employee.
- Blue/red box = unknown face.
- The right panel shows today's attendance count and latest entries.

---

## Registering an Employee

1. Click **Admin Login** → enter credentials.
2. In the sidebar, click **Register Employee**.
3. Enter the **Employee ID** and **Full Name**.
4. Click **Start Face Capture**.
5. Look at the camera; slowly rotate your head left and right.
6. The system captures 5 quality-checked samples automatically.
7. Click **Save Employee** when capture is complete.

---

## Database Location

```
AI_Face_Attendance/data/attendance.db
```

Tables:

| Table | Purpose |
|---|---|
| `employees` | Employee records |
| `face_embeddings` | Biometric face vectors (BLOB) |
| `attendance` | Daily attendance log |
| `admin_users` | Admin credentials (hashed) |
| `audit_log` | Action audit trail |
| `app_settings` | Runtime configuration |

---

## Backing Up the Database

```bat
copy data\attendance.db data\attendance_backup_%date:~10,4%%date:~4,2%%date:~7,2%.db
```

Or use any SQLite browser tool (e.g., DB Browser for SQLite).

---

## Running Tests

```bat
python -m pytest tests/ -v
```

Or run individual test modules:

```bat
python -m pytest tests/test_database.py   -v
python -m pytest tests/test_attendance.py -v
python -m pytest tests/test_auth.py       -v
python -m pytest tests/test_recognition.py -v
```

> Tests use isolated temporary databases and do **not** require a camera or the InsightFace model.

---

## Building a Windows Executable (Optional)

```bat
pip install pyinstaller
pyinstaller --onefile --windowed --name "FaceAttendance" main.py
```

The executable will appear in `dist/FaceAttendance.exe`.  
Include the `data/` directory alongside the executable when distributing.

---

## Liveness Detection (Anti-Spoofing)

**Current status: DISABLED.**  
The `recognition/liveness.py` module provides a structural hook for integrating a liveness model.  
Without it, attendance spoofing via photographs is possible.  
To enable: integrate the Silent-Face-Anti-Spoofing ONNX model as documented in `liveness.py`.

---

## Privacy & Security

- Face embeddings (biometric vectors) are stored **locally** in `attendance.db`.
- Raw photographs are **not retained** after registration.
- Admin credentials are stored as bcrypt hashes; plaintext passwords are never saved.
- Exported files are saved to `data/exports/` by default; protect them appropriately.
- All admin actions are logged in the `audit_log` table.
- Employees should be informed about facial recognition data collection as required by local law.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| Liveness detection | Not implemented — photo spoofing is possible |
| Multi-camera | Only one camera index supported at runtime (configurable in Settings) |
| First-launch model download | Requires internet; ~200 MB for buffalo_sc |
| Python 3.13 | Fully supported; Python 3.11/3.12 also work |
| Recognition accuracy | Degrades significantly in low light or extreme angles |
| OpenCV fallback | Used if InsightFace fails to load; much lower accuracy |

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Camera not opening | Check device index in Settings (default: 0). Close other apps using the camera. |
| Model download fails | Check internet connection. Model path: `C:\Users\<you>\.insightface\models\` |
| `insightface` install fails | Install Visual C++ Build Tools; try `pip install insightface --no-build-isolation` |
| Database locked | Only one application instance can run at a time |
| Faces not recognized | Re-register with better lighting. Lower the threshold in Settings. |
