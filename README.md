# ⚡ GEX PRO v7.0 — Dealer Intelligence Dashboard

Nifty Options ke liye complete GEX, IV, Vanna aur Gamma Density dashboard.  
Upstox API se live data • Historical Replay • Auto Refresh

---

## 📱 Android Phone pe Kaise Chalayein

### ✅ Sirf Ek Baar Karna Hai (Setup)

---

### 🔽 STEP 1 — Pydroid 3 Install Karo

1. Play Store kholo
2. **Pydroid 3** search karo
3. Install karo (bilkul free)

---

### 📂 STEP 2 — GEX Folder Banao

1. Phone ka **File Manager** kholo
2. **Internal Storage** pe jao
3. Khaali jagah pe **2 second tak dabaao** (long press)
4. **"New Folder"** pe tap karo
5. Naam likho: `GEX`
6. ✅ Done

Ab tumhara folder yahan hai:
```
Internal Storage → GEX
```

---

### 📥 STEP 3 — Files Download Karo (GitHub se)

Phone ke **Chrome browser** mein yeh links kholo aur download karo:

#### File 1 — Main App:
```
https://raw.githubusercontent.com/TUMHARA_USERNAME/gex-pro/main/app.py
```
> Chrome mein link kholo → 3 dot menu → **"Download"** tap karo

#### File 2 — Requirements:
```
https://raw.githubusercontent.com/TUMHARA_USERNAME/gex-pro/main/requirements.txt
```

#### File 3 — Run Script:
```
https://raw.githubusercontent.com/TUMHARA_USERNAME/gex-pro/main/run.sh
```

**Teeno files ko Internal Storage → GEX folder mein move karo.**

> 💡 **Easy option:** Browser mein `github.com/TUMHARA_USERNAME/gex-pro` kholo → Green **"Code"** button → **"Download ZIP"** → ZIP extract karo → teeno files GEX folder mein rakho.

---

### ▶️ STEP 4 — Pehli Baar Run Karo

1. **Pydroid 3** kholo
2. Upar **≡ (teen lakeerein)** dabaao
3. **Terminal** pe tap karo
4. Yeh type karo aur Enter dabaao:

```bash
bash /sdcard/GEX/run.sh
```

Yeh script apne aap:
- ✅ Saari libraries install karegi (sirf pehli baar)
- ✅ App start karegi
- ✅ Ek message dikhayegi: `Browser mein kholo: localhost:8501`

---

### 🌐 STEP 5 — Dashboard Kholo

1. Phone ka **Chrome** kholo
2. Address bar mein likho:
```
localhost:8501
```
3. Enter dabaao — **Dashboard khul jaayega!** 🎉

---

## 🔁 Roz Kaise Chalayein (Sirf Yeh Karo)

```
Pydroid 3 → Terminal → bash /sdcard/GEX/run.sh → Enter
```

**Bas itna! Setup dobara nahi hoga.**

---

## 📲 Dashboard Use Karna

1. Left sidebar mein **🔑 Upstox Token** paste karo
2. **📋 Load Expiries** dabaao
3. Dropdown se **expiry select** karo
4. **🔄 Refresh** dabaao
5. **⏱ Auto ON** karo — har 60 seconds mein khud refresh hoga

---

## 🛑 Band Karna Ho Toh

Pydroid Terminal mein:
```
Ctrl + C
```

---

## ❗ Problems aur Solutions

| Problem | Solution |
|---|---|
| `bash: command not found` | `sh /sdcard/GEX/run.sh` try karo |
| Libraries install nahi ho rahi | WiFi check karo, dobara run karo |
| `localhost:8501` nahi khula | `127.0.0.1:8501` try karo |
| App slow hai | Background apps band karo |
| Token error | Upstox se fresh token copy karo |
| Files nahi mili | GEX folder mein teeno files hain ya nahi check karo |

---

## 📁 Files Ki List

```
GEX/
├── app.py              ← Main dashboard
├── requirements.txt    ← Libraries list
├── run.sh              ← One-tap start script
└── GEX_HISTORY/        ← Data yahaan save hoga (khud ban jaayega)
    ├── snapshots/
    ├── daily_summary/
    └── alerts_log.csv
```

---

## ⚙️ Features

- 📊 **Live Option Chain** — ±15 strikes, color-coded
- ⚡ **GEX Chart** — Buy/Sell/Neutral + Historical overlay
- 📉 **IV Smile** — IV Bottom★, ATM IV, Common IV, Skew
- 🧲 **Gamma Density** — Convexity Zone, ±1σ range
- 📅 **Historical Replay** — Pichle din ke snapshots
- 🚨 **Auto Alerts** — Wall shifts, GEX flips, Volume spikes
- 🔄 **Auto Refresh** — Har 30-300 seconds (aap set karo)

---

## 🔑 Key Rules (Yaad Rakho)

```
+ve GEX  → Range day    → Dealers sell rallies, buy dips
-ve GEX  → Trend day    → Dealers amplify moves
IV Bottom★ → Expected expiry pin — SABSE IMPORTANT level!
PCR > 1.3  → Bullish    PCR < 0.7 → Bearish
Gamma Peak → Magnetic pull — spot yahaan aata hai
```

---

*GEX PRO v7.0 — Built for Indian Options Traders*
