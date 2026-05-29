Flight Extension Tool
Monthly campaign flight extension tool — upload LI-Setting sheets, apply June budgets, configure mid-flight splits, and export to Google Sheets.
---
🚀 Deploy to Streamlit Cloud (free)
Step 1 — Push to GitHub
Create a new public GitHub repo (e.g. `flight-extension-tool`)
Upload these two files:
`app.py`
`requirements.txt`
```
flight-extension-tool/
├── app.py
└── requirements.txt
```
Step 2 — Deploy on Streamlit Cloud
Go to share.streamlit.io
Sign in with GitHub
Click "New app"
Select your repo → branch `main` → file `app.py`
Click Deploy — it'll be live in ~60 seconds
Your app will be at:
```
https://<your-username>-flight-extension-tool-app-<hash>.streamlit.app
```
---
💻 Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
---
📋 How to use
Month Configuration — set previous month end date (filter), new month start/end, and minimum flight budget (€25 default)
Upload Campaign-Settings sheets — drop one or more `.xlsx` files with a `LI-Setting` tab. Each file handles up to 15 IOs. Multiple files accumulate.
Picks the most recent `Active Flight End Date ≤ previous month end` per LI (handles campaigns paused in May but active in prior months)
June budgets pre-filled from previous month
Upload June Budget Reference — sheet with `IO Name` + `June Budget` columns
Hit ⚡ Apply June Budgets to distribute proportionally across LIs by May ratio
Flags IOs in reference but not loaded, and loaded IOs missing from reference
Configure per-IO — select each IO to:
Toggle mid-flight split (cut day + % for first period)
Adjust individual LI budgets manually
See live flight preview per LI (with min budget collapse warning)
Export — download CSV or TSV, filter by All / Match / Changed
---
📤 Google Sheets paste
Download the TSV → open in any text editor → Select All → Copy → paste into Google Sheets cell A1.
Columns: `LI ID · Start Date · End Date · Budget · Daily Budget`
