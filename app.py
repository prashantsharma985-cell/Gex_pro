# =============================================================================
# GEX PRO DASHBOARD v7.0 — STREAMLIT EDITION
# =============================================================================
#
# ✅ HOW TO RUN (Step by step — ek baar karo, hamesha kaam karega):
#
#   STEP 1 — Python install karo (agar nahi hai):
#             https://www.python.org/downloads/  → Download karke install karo
#             Install ke time "Add Python to PATH" checkbox ZAROOR tick karo ✅
#
#   STEP 2 — Libraries install karo (sirf pehli baar):
#             Windows: Start menu → "cmd" search karo → Command Prompt kholo
#             Mac/Linux: Terminal kholo
#             Yeh command type karo aur Enter dabaao:
#
#             pip install streamlit plotly pandas numpy scipy requests
#
#   STEP 3 — Yeh file kisi folder mein save karo
#             Example: C:\GEX\gex_pro_streamlit.py
#
#   STEP 4 — App run karo:
#             Command Prompt mein type karo:
#             streamlit run C:\GEX\gex_pro_streamlit.py
#             (apna actual path daalo)
#
#   STEP 5 — Browser automatically khulega!
#             Agar nahi khula toh browser mein jaao: http://localhost:8501
#
#   STEP 6 — Dashboard use karo:
#             Left sidebar mein Token paste karo
#             → Expiry load karo
#             → Refresh dabaao
#             → Auto ON karo (every 60 seconds auto refresh)
#
# DATA SAVED TO: GEX_HISTORY/ folder (same folder jahan ye file hai)
#   snapshots/     — Full chain per minute
#   daily_summary/ — Key metrics per minute
#   alerts_log.csv — All alerts
#
# =============================================================================

import os, threading, warnings, requests, time
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from scipy.ndimage import gaussian_filter1d

warnings.filterwarnings("ignore")

# ── PAGE CONFIG (must be first Streamlit call) ────────────────
st.set_page_config(
    page_title="GEX PRO v7.0",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CONFIG ────────────────────────────────────────────────────
LOT_SIZE         = 65
REFRESH_SEC      = 60
INSTRUMENT_KEY   = "NSE_INDEX|Nifty 50"
SMOOTH_SIGMA     = 1.2
STRIKE_STEP      = 100
VOL_SPIKE_X      = 2.0
IV_SPIKE_X       = 1.5
CHAIN_STRIKES    = 15
IV_CHART_STRIKES = 10

# Data folder — same directory as this script
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
HISTORY_FOLDER = os.path.join(BASE_DIR, "GEX_HISTORY")

for _d in [HISTORY_FOLDER,
           f"{HISTORY_FOLDER}/snapshots",
           f"{HISTORY_FOLDER}/daily_summary",
           f"{HISTORY_FOLDER}/historical"]:
    os.makedirs(_d, exist_ok=True)

# ── CHART COLORS ──────────────────────────────────────────────
C = dict(
    spot="#e63946", buy="#27ae60", sell="#e74c3c", neutral="#78909c",
    density="#ff8f00", convex="#00c853", cwall="#1565c0", pwall="#e67e22",
    gpeak="#7b2d8b", ivbot="#00897b", maxpain="#e91e63", flip="#f9a825",
    h0="#64b5f6", h1="#ffb74d", h2="#ba68c8", h3="#81c784",
    vanna="#5c6bc0",
    bg_sig="rgba(44,130,201,0.06)",
)

# ── SESSION STATE INIT ────────────────────────────────────────
if "history_cache" not in st.session_state:
    st.session_state.history_cache = []   # [(df, time_str), ...]
if "prev_an" not in st.session_state:
    st.session_state.prev_an = {}
if "shifts_log" not in st.session_state:
    st.session_state.shifts_log = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None
if "auto_on" not in st.session_state:
    st.session_state.auto_on = False

# =============================================================================
# API FUNCTIONS
# =============================================================================
def make_headers(token):
    return {"Accept": "application/json",
            "Authorization": f"Bearer {token.strip()}"}

def get_spot(headers):
    r = requests.get(
        f"https://api-v2.upstox.com/market-quote/ltp"
        f"?instrument_key={INSTRUMENT_KEY}",
        headers=headers, timeout=10)
    r.raise_for_status()
    return float(r.json()["data"]["NSE_INDEX:Nifty 50"]["last_price"])

def get_expiries(headers):
    r = requests.get(
        f"https://api-v2.upstox.com/option/contract"
        f"?instrument_key={INSTRUMENT_KEY}",
        headers=headers, timeout=10)
    r.raise_for_status()
    return sorted(pd.DataFrame(r.json()["data"])["expiry"].unique())

def get_chain(expiry, headers):
    r = requests.get(
        f"https://api-v2.upstox.com/option/chain"
        f"?instrument_key={INSTRUMENT_KEY}&expiry_date={expiry}",
        headers=headers, timeout=10)
    r.raise_for_status()
    rows = []
    for row in r.json()["data"]:
        cm = row["call_options"]["market_data"]
        cg = row["call_options"]["option_greeks"]
        pm = row["put_options"]["market_data"]
        pg = row["put_options"]["option_greeks"]
        rows.append({
            "Strike"     : float(row["strike_price"]),
            "Call_OI"    : float(cm.get("oi", 0) or 0),
            "Call_OI_Chg": float(cm.get("oi", 0) or 0) - float(cm.get("prev_oi", 0) or 0),
            "Call_Vol"   : float(cm.get("volume", 0) or 0),
            "Call_LTP"   : float(cm.get("ltp", 0) or 0),
            "Call_IV"    : float(cg.get("iv", 0) or 0),
            "Call_Gamma" : float(cg.get("gamma", 0) or 0),
            "Call_Delta" : float(cg.get("delta", 0) or 0),
            "Call_Vega"  : float(cg.get("vega", 0) or 0),
            "Put_OI"     : float(pm.get("oi", 0) or 0),
            "Put_OI_Chg" : float(pm.get("oi", 0) or 0) - float(pm.get("prev_oi", 0) or 0),
            "Put_Vol"    : float(pm.get("volume", 0) or 0),
            "Put_LTP"    : float(pm.get("ltp", 0) or 0),
            "Put_IV"     : float(pg.get("iv", 0) or 0),
            "Put_Gamma"  : float(pg.get("gamma", 0) or 0),
            "Put_Delta"  : float(pg.get("delta", 0) or 0),
            "Put_Vega"   : float(pg.get("vega", 0) or 0),
        })
    return pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)

# =============================================================================
# CALCULATION ENGINE
# =============================================================================
def compute(chain, spot):
    df = chain.copy()

    df["Buy_GEX"]  = df["Call_OI"] * df["Call_Gamma"] * spot**2 * 0.01 * LOT_SIZE
    df["Sell_GEX"] = df["Put_OI"]  * df["Put_Gamma"]  * spot**2 * 0.01 * LOT_SIZE
    df["Net_GEX"]  = df["Buy_GEX"] - df["Sell_GEX"]
    df["Neutral"]  = df["Buy_GEX"] + df["Sell_GEX"]

    df["RawDensity"]   = df["Call_OI"]*df["Call_Gamma"] + df["Put_OI"]*df["Put_Gamma"]
    df["GammaDensity"] = gaussian_filter1d(df["RawDensity"].values, sigma=SMOOTH_SIGMA)
    pk = df["GammaDensity"].max()
    df["Convexity"]    = np.where(df["GammaDensity"] >= 0.40*pk, df["GammaDensity"], 0.0)

    df["Avg_IV"]  = np.where((df["Call_IV"] > 0) & (df["Put_IV"] > 0),
                              (df["Call_IV"] + df["Put_IV"]) / 2,
                              np.maximum(df["Call_IV"], df["Put_IV"]))
    df["IV_Skew"] = df["Call_IV"] - df["Put_IV"]

    df["Total_OI"]   = df["Call_OI"]  + df["Put_OI"]
    df["Total_Vol"]  = df["Call_Vol"] + df["Put_Vol"]
    df["Call_Score"] = df["Call_OI"]  * df["Call_Gamma"]
    df["Put_Score"]  = df["Put_OI"]   * df["Put_Gamma"]

    df["Call_Vanna"] = np.where(df["Call_IV"] > 0,
        df["Call_Vega"]*df["Call_Delta"] / (spot*(df["Call_IV"]/100) + 1e-9), 0)
    df["Put_Vanna"]  = np.where(df["Put_IV"] > 0,
        df["Put_Vega"]*df["Put_Delta"]  / (spot*(df["Put_IV"] /100) + 1e-9), 0)
    df["Net_Vanna"]  = (df["Call_OI"]*df["Call_Vanna"]
                       - df["Put_OI"]*df["Put_Vanna"]) * LOT_SIZE

    common_iv = df["Avg_IV"][df["Avg_IV"] > 0].mean() if (df["Avg_IV"] > 0).any() else 15.0
    df["Common_IV"] = common_iv

    cs = df.nlargest(3, "Call_OI"); ps = df.nlargest(3, "Put_OI")
    call_wall  = float(cs.iloc[0]["Strike"])
    call_wall2 = float(cs.iloc[1]["Strike"]) if len(cs) > 1 else call_wall
    put_wall   = float(ps.iloc[0]["Strike"])
    put_wall2  = float(ps.iloc[1]["Strike"])  if len(ps) > 1 else put_wall
    smart_cw   = float(df.loc[df["Call_Score"].idxmax(), "Strike"])
    smart_pw   = float(df.loc[df["Put_Score"].idxmax(),  "Strike"])
    gamma_peak = float(df.loc[df["GammaDensity"].idxmax(), "Strike"])
    max_vol_s  = float(df.loc[df["Total_Vol"].idxmax(), "Strike"])
    max_cv_s   = float(df.loc[df["Call_Vol"].idxmax(),  "Strike"])
    max_pv_s   = float(df.loc[df["Put_Vol"].idxmax(),   "Strike"])

    viv       = df[df["Avg_IV"] > 2]
    iv_bottom = float(viv.loc[viv["Avg_IV"].idxmin(), "Strike"]) if not viv.empty else spot

    atm_i  = int((df["Strike"] - spot).abs().argsort().iloc[0])
    atm_iv = float(df.iloc[atm_i]["Avg_IV"]) if df.iloc[atm_i]["Avg_IV"] > 0 else 15.0

    sig1_lo = round(spot - spot*(atm_iv/100)*(1/252)**0.5, 0)
    sig1_hi = round(spot + spot*(atm_iv/100)*(1/252)**0.5, 0)

    pcr        = df["Put_OI"].sum() / (df["Call_OI"].sum() + 1e-9)
    net_gex_cr = df["Net_GEX"].sum() / 1e7
    net_vanna  = df["Net_Vanna"].sum() / 1e4

    net_raw = (df["Call_OI"]*df["Call_Gamma"] - df["Put_OI"]*df["Put_Gamma"]).values
    str_arr = df["Strike"].values
    cum_gex = np.cumsum(net_raw)
    flip_zones = []
    for idx in np.where(np.diff(np.sign(cum_gex)))[0]:
        s0,s1 = str_arr[idx], str_arr[idx+1]
        g0,g1 = cum_gex[idx], cum_gex[idx+1]
        flip_zones.append(round(float(s0 + (0-g0)*(s1-s0)/(g1-g0+1e-12)), 1))
    if not flip_zones:
        for idx in np.where(np.diff(np.sign(net_raw)))[0]:
            s0,s1 = str_arr[idx], str_arr[idx+1]
            g0,g1 = net_raw[idx], net_raw[idx+1]
            flip_zones.append(round(float(s0 + (0-g0)*(s1-s0)/(g1-g0+1e-12)), 1))

    max_pain = _max_pain(df)

    avg_vol    = df["Total_Vol"].mean()
    avg_iv     = df[df["Avg_IV"] > 0]["Avg_IV"].mean() if (df["Avg_IV"] > 0).any() else atm_iv
    vol_spikes = df.loc[df["Total_Vol"] > VOL_SPIKE_X*avg_vol, "Strike"].tolist()
    iv_spikes  = df.loc[df["Avg_IV"]    > IV_SPIKE_X*avg_iv,  "Strike"].tolist()

    an = dict(
        spot=spot, pcr=round(pcr,3), net_gex_cr=round(net_gex_cr,2),
        net_vanna=round(net_vanna,2),
        call_wall=call_wall, call_wall2=call_wall2,
        put_wall=put_wall,   put_wall2=put_wall2,
        smart_cw=smart_cw,   smart_pw=smart_pw,
        gamma_peak=gamma_peak, iv_bottom=iv_bottom,
        atm_iv=round(atm_iv,2), common_iv=round(common_iv,2),
        sig1_lo=sig1_lo, sig1_hi=sig1_hi,
        max_pain=max_pain, flip_zones=flip_zones[:4],
        max_vol_s=max_vol_s, max_cv_s=max_cv_s, max_pv_s=max_pv_s,
        call_1oi=float(cs.iloc[0]["Call_OI"]),
        call_2oi=float(cs.iloc[1]["Call_OI"]) if len(cs)>1 else 0,
        put_1oi =float(ps.iloc[0]["Put_OI"]),
        put_2oi =float(ps.iloc[1]["Put_OI"])  if len(ps)>1 else 0,
        vol_spikes=vol_spikes, iv_spikes=iv_spikes,
        time=datetime.now().strftime("%H:%M"),
        date=datetime.now().strftime("%Y-%m-%d"),
    )
    sig, prob, view, alerts = _signal(an, df)
    an.update(signal=sig, probability=prob, view=view, alerts=alerts)
    return dict(df=df, an=an)

def _max_pain(df):
    pain = {}
    for s in df["Strike"].values:
        pain[s] = (((s - df["Strike"]) * df["Call_OI"]).clip(lower=0).sum() +
                   ((df["Strike"] - s) * df["Put_OI"]).clip(lower=0).sum())
    return float(min(pain, key=pain.get))

def _signal(a, df):
    sc = 0; alerts = []

    if   a["pcr"] > 1.3:  sc+=2; alerts.append("🟢 PCR>1.3 — Strongly Bullish Positioning")
    elif a["pcr"] > 1.1:  sc+=1; alerts.append("🟢 PCR>1.1 — Mildly Bullish")
    elif a["pcr"] < 0.7:  sc-=2; alerts.append("🔴 PCR<0.7 — Strongly Bearish Positioning")
    elif a["pcr"] < 0.9:  sc-=1; alerts.append("🔴 PCR<0.9 — Mildly Bearish")
    else: alerts.append("⚪ PCR 0.9–1.1 — Neutral / No-Trade Zone")

    if a["net_gex_cr"] >= 0:
        sc+=1; alerts.append(f"📌 +ve GEX {a['net_gex_cr']:+.1f}Cr — Pinning / Range-Bound")
    else:
        sc-=1; alerts.append(f"💥 −ve GEX {a['net_gex_cr']:+.1f}Cr — Trending / Volatile")

    rng = a["call_wall"] - a["put_wall"]
    if rng > 0:
        pct = (a["spot"] - a["put_wall"]) / rng * 100
        if   pct > 78: sc-=1; alerts.append(f"⚠️ Near Call Wall {a['call_wall']:.0f} — Resistance")
        elif pct < 22: sc+=1; alerts.append(f"⚠️ Near Put Wall {a['put_wall']:.0f} — Support")
        else: alerts.append(f"✅ Spot inside Range [{a['put_wall']:.0f}–{a['call_wall']:.0f}]")

    d = a["iv_bottom"] - a["spot"]
    if abs(d) > 150:
        sc += (1 if d>0 else -1)
        alerts.append(f"🎯 IV Bottom @{a['iv_bottom']:.0f} — {'UP' if d>0 else 'DOWN'}ward drift ({abs(d):.0f}pts)")
    else:
        alerts.append(f"🎯 IV Bottom @{a['iv_bottom']:.0f} — Near Spot (Pin Expected)")

    gd = a["gamma_peak"] - a["spot"]
    if abs(gd) < 75: alerts.append(f"🧲 Gamma Peak @{a['gamma_peak']:.0f} — Strong Pin (Spot at Magnet)")
    else: alerts.append(f"🧲 Gamma Pull {'UP→' if gd>0 else 'DOWN→'}{a['gamma_peak']:.0f} ({abs(gd):.0f}pts)")

    if a["net_vanna"] > 0: alerts.append(f"🌀 Vanna +{a['net_vanna']:.1f} — IV rise = Dealers BUY (Bullish)")
    else:                  alerts.append(f"🌀 Vanna {a['net_vanna']:.1f} — IV rise = Dealers SELL (Bearish)")

    if a["atm_iv"] > 22:   alerts.append(f"🚨 High ATM IV {a['atm_iv']:.1f}% — Event Risk / Wide Range")
    elif a["atm_iv"] < 10: alerts.append(f"😴 Low ATM IV {a['atm_iv']:.1f}% — Breakout Risk")

    if a["vol_spikes"]:
        alerts.append(f"🔥 VOL SPIKE @{', '.join(f'{s:.0f}' for s in a['vol_spikes'][:3])} — Smart Money!")
    if a["iv_spikes"]:
        alerts.append(f"⚡ IV SPIKE @{', '.join(f'{s:.0f}' for s in a['iv_spikes'][:3])} — Sudden Demand!")

    if   sc >= 3:  sig,view,prob = "🚀 STRONG BULLISH","BULLISH",min(82,55+sc*8)
    elif sc >= 1:  sig,view,prob = "📈 MILDLY BULLISH","BULLISH",min(68,50+sc*5)
    elif sc <= -3: sig,view,prob = "🔻 STRONG BEARISH","BEARISH",min(82,55+abs(sc)*8)
    elif sc <= -1: sig,view,prob = "📉 MILDLY BEARISH","BEARISH",min(68,50+abs(sc)*5)
    else:          sig,view,prob = "⚖️ NEUTRAL / RANGE","NEUTRAL",50
    return sig, prob, view, alerts

# =============================================================================
# SHIFT DETECTION
# =============================================================================
def detect_shifts(an):
    sh = []
    prev = st.session_state.prev_an
    if prev:
        if an["call_wall"] != prev.get("call_wall"):
            d = "⬆ UP" if an["call_wall"] > prev["call_wall"] else "⬇ DOWN"
            sh.append(f"🔵 CALL WALL {d}: {prev['call_wall']:.0f}→{an['call_wall']:.0f}")
        if an["put_wall"] != prev.get("put_wall"):
            d = "⬆ UP" if an["put_wall"] > prev["put_wall"] else "⬇ DOWN"
            sh.append(f"🟠 PUT WALL {d}: {prev['put_wall']:.0f}→{an['put_wall']:.0f}")
        if an["gamma_peak"] != prev.get("gamma_peak"):
            d = "⬆" if an["gamma_peak"] > prev["gamma_peak"] else "⬇"
            sh.append(f"🟣 GAMMA PEAK {d}: {prev['gamma_peak']:.0f}→{an['gamma_peak']:.0f} — Magnet Moved!")
        iv_d = an["iv_bottom"] - prev.get("iv_bottom", an["iv_bottom"])
        if abs(iv_d) > 100:
            sh.append(f"🎯★ IV BOTTOM SHIFTED {'⬆UP' if iv_d>0 else '⬇DOWN'} {abs(iv_d):.0f}pts: "
                      f"{prev['iv_bottom']:.0f}→{an['iv_bottom']:.0f} — PIN ZONE CHANGED!")
        if prev.get("call_1oi",0) > 0 and an["call_1oi"] < prev["call_1oi"]*0.95:
            pct = (prev["call_1oi"]-an["call_1oi"])/prev["call_1oi"]*100
            sh.append(f"⚠️ CALL OI UNWINDING @{an['call_wall']:.0f}: -{pct:.1f}% — Ceiling Weakening!")
        if prev.get("put_1oi",0) > 0 and an["put_1oi"] < prev["put_1oi"]*0.95:
            pct = (prev["put_1oi"]-an["put_1oi"])/prev["put_1oi"]*100
            sh.append(f"⚠️ PUT OI UNWINDING @{an['put_wall']:.0f}: -{pct:.1f}% — Floor Weakening!")
        p, c = prev.get("net_gex_cr", an["net_gex_cr"]), an["net_gex_cr"]
        if p >= 0 and c < 0:  sh.append("🚨 GEX FLIP: Pinning→Trending! Explosive move!")
        elif p < 0 and c >= 0: sh.append("🟢 GEX FLIP: Trending→Pinning! Range forming!")
        if an["vol_spikes"]:
            sh.append(f"🔥 SUDDEN VOL SPIKE @{', '.join(f'{s:.0f}' for s in an['vol_spikes'][:3])}")
        if an["iv_spikes"]:
            sh.append(f"⚡ SUDDEN IV SPIKE @{', '.join(f'{s:.0f}' for s in an['iv_spikes'][:3])}")

    st.session_state.prev_an = dict(
        call_wall=an["call_wall"], put_wall=an["put_wall"],
        gamma_peak=an["gamma_peak"], iv_bottom=an["iv_bottom"],
        net_gex_cr=an["net_gex_cr"],
        call_1oi=an["call_1oi"], put_1oi=an["put_1oi"])
    return sh

# =============================================================================
# HISTORY
# =============================================================================
def save_snap(an, df, expiry, shifts):
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    df.to_csv(f"{HISTORY_FOLDER}/snapshots/{ts}_{expiry}.csv", index=False)
    sf = f"{HISTORY_FOLDER}/daily_summary/summary_{an['date']}.csv"
    row = pd.DataFrame([{k:v for k,v in an.items() if not isinstance(v,(list,dict))}])
    row["expiry"] = expiry
    row.to_csv(sf, mode="a", header=not os.path.exists(sf), index=False)
    if shifts:
        af = f"{HISTORY_FOLDER}/alerts_log.csv"
        pd.DataFrame([{"dt":f"{an['date']} {an['time']}", "spot":an["spot"], "alert":s}
                       for s in shifts]).to_csv(af, mode="a",
                       header=not os.path.exists(af), index=False)
    st.session_state.history_cache.append((df.copy(), an["time"]))
    if len(st.session_state.history_cache) > 13:
        st.session_state.history_cache.pop(0)

def load_history():
    f = f"{HISTORY_FOLDER}/daily_summary/summary_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()

def get_available_dates():
    folder = f"{HISTORY_FOLDER}/daily_summary"
    if not os.path.exists(folder): return []
    files = sorted([x.replace("summary_","").replace(".csv","")
                    for x in os.listdir(folder) if x.endswith(".csv")])
    return files[-30:] if files else []

def get_snapshots_for_date(date):
    folder = f"{HISTORY_FOLDER}/snapshots"
    if not os.path.exists(folder): return []
    files = sorted([x for x in os.listdir(folder) if x.startswith(date.replace("-",""))])
    return [fp[9:14].replace("_",":") for fp in files]

def load_snapshot(date, time_str):
    folder = f"{HISTORY_FOLDER}/snapshots"
    ts = date.replace("-","") + "_" + time_str.replace(":","")
    matches = [x for x in os.listdir(folder) if x.startswith(ts)]
    if matches:
        return pd.read_csv(os.path.join(folder, matches[0]))
    return pd.DataFrame()

# =============================================================================
# CHART HELPERS
# =============================================================================
def _apply_theme(fig, title, h=500, dtick=STRIKE_STEP):
    fig.update_layout(
        title=dict(text=title,
                   font=dict(size=13, color="#0d1b4b", family="Inter,Arial", weight="bold"),
                   x=0.01),
        paper_bgcolor="#ffffff", plot_bgcolor="#f7f9fc",
        font=dict(color="#1e2a3b", size=11, family="Inter,Arial"),
        height=h, margin=dict(l=58, r=14, t=50, b=52),
        legend=dict(bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0",
                    borderwidth=1, font=dict(size=10), orientation="h", y=-0.14, x=0),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.97)", bordercolor="#d0d7e3",
                        font=dict(size=11, color="#1e2a3b")),
    )
    fig.update_xaxes(gridcolor="#eef0f4", linecolor="#d0d7e3", zeroline=False,
                     dtick=dtick, fixedrange=False, showspikes=True,
                     spikecolor="#94a3b8", spikedash="dot", spikethickness=1,
                     tickfont=dict(size=10, color="#6b7280"))
    fig.update_yaxes(gridcolor="#eef0f4", linecolor="#d0d7e3", fixedrange=False,
                     zeroline=True, zerolinecolor="#cbd5e1", zerolinewidth=1.2,
                     tickfont=dict(size=10, color="#6b7280"))
    return fig

def _vl(fig, x, lbl, col, lw=1.5, dash="dot", row=None, col_n=None):
    kw = dict(row=row, col=col_n) if row else {}
    fig.add_vline(x=x, line=dict(color=col, width=lw, dash=dash),
                  annotation=dict(
                      text=f"<b>{lbl}</b><br>{x:.0f}",
                      font=dict(color=col, size=9, family="Inter,Arial", weight="bold"),
                      bgcolor="rgba(255,255,255,0.93)",
                      bordercolor=col, borderwidth=1.2, borderpad=3,
                      opacity=0.95), **kw)

# =============================================================================
# CHART 1 — GEX + OI STRUCTURE
# =============================================================================
def ch_gex_oi(df, an):
    spot = an["spot"]
    hcache = st.session_state.history_cache
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.60, 0.40], vertical_spacing=0.05,
                        subplot_titles=["GEX Exposure (Buy/Sell/Neutral) + Historical",
                                        "OI Structure (Call↑ Put↓) + Wall Shifts"])

    hcols = [C["h0"], C["h1"], C["h2"], C["h3"]]
    for i,(hdf,ht) in enumerate(hcache[-4:]):
        if hdf is None or "Strike" not in hdf.columns: continue
        try:
            for oc,gc in [("Call_OI","Call_Gamma"),("Put_OI","Put_Gamma")]:
                if oc in hdf.columns and gc in hdf.columns:
                    nh = hdf[oc]*hdf[gc]*spot**2*0.01*LOT_SIZE
                    fig.add_trace(go.Scatter(x=hdf["Strike"], y=nh,
                        name=f"GEX@{ht}", line=dict(color=hcols[i%4],width=1,dash="dot"),
                        opacity=0.35, showlegend=(i==0), legendgroup="hist_gex"),
                        row=1, col=1)
        except: pass

    fig.add_trace(go.Scatter(x=df["Strike"], y=df["Neutral"],
                             name="Neutral", line=dict(color=C["neutral"],width=1.5),
                             fill="tozeroy", fillcolor="rgba(120,144,156,0.09)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Strike"], y=df["Buy_GEX"],
                             name="Buy (Call γ)", line=dict(color=C["buy"],width=2.5),
                             fill="tozeroy", fillcolor="rgba(39,174,96,0.11)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Strike"], y=df["Sell_GEX"],
                             name="Sell (Put γ)", line=dict(color=C["sell"],width=2.5),
                             fill="tozeroy", fillcolor="rgba(231,76,60,0.11)"), row=1, col=1)

    fig.add_vrect(x0=an["sig1_lo"], x1=an["sig1_hi"],
                  fillcolor=C["bg_sig"], line=dict(color="#7fb3d3",width=0.8), row=1, col=1)

    for x,lb,cl in [(spot,"Spot",C["spot"]), (an["call_wall"],"CW",C["cwall"]),
                    (an["put_wall"],"PW",C["pwall"]), (an["gamma_peak"],"γPeak",C["gpeak"])]:
        _vl(fig,x,lb,cl,row=1,col_n=1)
    for fz in an["flip_zones"][:2]:
        _vl(fig,fz,"Flip",C["flip"],lw=1.2,row=1,col_n=1)

    for vs in an["vol_spikes"][:2]:
        fig.add_annotation(x=vs, y=df["Buy_GEX"].max()*0.75,
            text=f"🔥{vs:.0f}", font=dict(size=9,color="#ea580c",weight="bold"),
            bgcolor="rgba(255,247,237,0.95)", bordercolor="#ea580c",
            showarrow=True, arrowcolor="#ea580c", arrowsize=0.7, row=1, col=1)

    hcols_cw = ["rgba(21,101,192,0.22)","rgba(21,101,192,0.15)","rgba(21,101,192,0.10)"]
    hcols_pw = ["rgba(230,126,34,0.22)","rgba(230,126,34,0.15)","rgba(230,126,34,0.10)"]
    for i,(hdf,ht) in enumerate(hcache[-3:]):
        if hdf is None: continue
        try:
            c1 = "Call_OI" if "Call_OI" in hdf.columns else None
            p1 = "Put_OI"  if "Put_OI"  in hdf.columns else None
            if c1 and p1:
                hcw = float(hdf.loc[hdf[c1].idxmax(),"Strike"])
                hpw = float(hdf.loc[hdf[p1].idxmax(),"Strike"])
                fig.add_vline(x=hcw, line=dict(color=hcols_cw[i%3],width=1,dash="dot"), row=2, col=1)
                fig.add_vline(x=hpw, line=dict(color=hcols_pw[i%3],width=1,dash="dot"), row=2, col=1)
        except: pass

    fig.add_trace(go.Bar(x=df["Strike"], y=df["Call_OI"]/1e5,
                         name="Call OI (L)", marker=dict(color=C["cwall"],opacity=0.72), width=40), row=2, col=1)
    fig.add_trace(go.Bar(x=df["Strike"], y=-df["Put_OI"]/1e5,
                         name="Put OI (L)", marker=dict(color=C["pwall"],opacity=0.72), width=40), row=2, col=1)
    fig.add_hline(y=0, line=dict(color="#888",width=1), row=2, col=1)

    for x,lb,cl in [(spot,"Spot",C["spot"]), (an["call_wall"],"CW",C["cwall"]),
                    (an["put_wall"],"PW",C["pwall"]), (an["max_pain"],"Pain",C["maxpain"])]:
        _vl(fig,x,lb,cl,row=2,col_n=1)

    mvr = df[df["Strike"]==an["max_vol_s"]]
    if not mvr.empty:
        fig.add_annotation(x=an["max_vol_s"], y=float(mvr["Call_OI"].iloc[0])/1e5+0.3,
                           text=f"<b>★{an['max_vol_s']:.0f}</b>",
                           font=dict(size=9,color="#ea580c",weight="bold"),
                           bgcolor="rgba(255,247,237,0.95)", bordercolor="#ea580c",
                           showarrow=True, arrowcolor="#ea580c", arrowsize=0.7, row=2, col=1)

    regime = "📌 Pinning" if an["net_gex_cr"]>=0 else "💥 Trending"
    flips  = ", ".join(f"{z:.0f}" for z in an["flip_zones"][:2]) or "None"
    return _apply_theme(fig,
        f"⚡ <b>GEX + OI Structure</b>  |  Net:{an['net_gex_cr']:+.2f}Cr  "
        f"{regime}  |  Flip:{flips}  PCR:{an['pcr']:.2f}  MaxVol@{an['max_vol_s']:.0f}  |  {an['time']}", h=560)

# =============================================================================
# CHART 2 — IV CHART
# =============================================================================
def ch_iv(df, an):
    spot = an["spot"]
    hcache = st.session_state.history_cache
    atm_i = int((df["Strike"] - spot).abs().argsort().iloc[0])
    lo    = max(0, atm_i - IV_CHART_STRIKES)
    hi    = min(len(df), atm_i + IV_CHART_STRIKES + 1)
    iv_   = df.iloc[lo:hi].copy()
    iv_   = iv_[iv_["Avg_IV"] > 1]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.65, 0.35], vertical_spacing=0.06,
                        subplot_titles=["IV Smile ±10 Strikes  (Common IV + ATM IV + IV Bottom ★)",
                                        "IV Skew = Call IV − Put IV"])

    if len(hcache) >= 2:
        hcols = [C["h0"], C["h1"], C["h2"], C["h3"]]
        for i,(hdf,ht) in enumerate(hcache[-4:]):
            if hdf is None or "Avg_IV" not in hdf.columns: continue
            try:
                viv = hdf[hdf["Avg_IV"] > 2]
                if not viv.empty:
                    ivb_h = float(viv.loc[viv["Avg_IV"].idxmin(),"Strike"])
                    fig.add_vline(x=ivb_h, line=dict(color=hcols[i%4],width=1.2,dash="longdash"),
                                  annotation=dict(text=f"IVBot@{ht}", font=dict(color=hcols[i%4],size=8)),
                                  row=1, col=1)
            except: pass

    fig.add_trace(go.Scatter(x=iv_["Strike"], y=iv_["Call_IV"],
                             name="Call IV", line=dict(color=C["cwall"],width=2.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=iv_["Strike"], y=iv_["Put_IV"],
                             name="Put IV", line=dict(color=C["sell"],width=2.2)), row=1, col=1)
    fig.add_hline(y=an["common_iv"], line=dict(color="#9c27b0",width=1.8,dash="dash"),
                  annotation=dict(text=f"Common IV {an['common_iv']:.1f}%",
                                  font=dict(color="#9c27b0",size=10,weight="bold"),
                                  bgcolor="rgba(255,255,255,0.9)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[spot], y=[an["atm_iv"]], mode="markers",
                             name=f"ATM IV {an['atm_iv']:.1f}%",
                             marker=dict(color="#f39c12",size=14,symbol="star",
                                         line=dict(color="white",width=1.5))), row=1, col=1)
    if not iv_.empty:
        ibr = iv_.loc[iv_["Avg_IV"].idxmin()]
        fig.add_trace(go.Scatter(x=[ibr["Strike"]], y=[ibr["Avg_IV"]],
            mode="markers+text", name=f"★ IV Bottom {ibr['Strike']:.0f}",
            text=[f"  ★ {ibr['Strike']:.0f}"], textposition="middle right",
            textfont=dict(color=C["ivbot"],size=11,weight="bold"),
            marker=dict(color=C["ivbot"],size=16,symbol="triangle-down",
                        line=dict(color="white",width=2))), row=1, col=1)

    iv2 = df.iloc[lo:hi].copy()
    iv2 = iv2[(iv2["Call_IV"]>0) & (iv2["Put_IV"]>0)]
    fig.add_trace(go.Bar(x=iv2["Strike"], y=iv2["IV_Skew"], name="Skew(C−P)",
                         marker_color=[C["cwall"] if v>=0 else C["sell"] for v in iv2["IV_Skew"]],
                         opacity=0.72), row=2, col=1)
    fig.add_hline(y=0, line=dict(color="#aaa",width=1), row=2, col=1)

    for r in [1, 2]:
        _vl(fig,spot,"Spot",C["spot"],lw=2,dash="dash",row=r,col_n=1)
        _vl(fig,an["call_wall"],"CW",C["cwall"],row=r,col_n=1)
        _vl(fig,an["put_wall"],"PW",C["pwall"],row=r,col_n=1)
        _vl(fig,an["iv_bottom"],"IVBot",C["ivbot"],lw=1.8,dash="longdash",row=r,col_n=1)

    return _apply_theme(fig,
        f"📊 <b>IV Chart ±10 Strikes</b>  |  IV Bottom★:{an['iv_bottom']:.0f}  "
        f"ATM:{an['atm_iv']:.1f}%  Common:{an['common_iv']:.1f}%  |  {an['time']}", h=520)

# =============================================================================
# CHART 3 — GAMMA DENSITY + OI DENSITY
# =============================================================================
def ch_density_oi(df, an):
    spot   = an["spot"]
    pk     = df["GammaDensity"].max()
    hcache = st.session_state.history_cache
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.55, 0.45], vertical_spacing=0.05,
                        subplot_titles=["Gamma Density + Convexity Zone (Historical inside)",
                                        "OI Density + Max Pain"])

    hcols = [C["h0"], C["h1"], C["h2"], C["h3"]]
    for i,(hdf,ht) in enumerate(hcache[-4:]):
        if hdf is None or "Strike" not in hdf.columns: continue
        try:
            raw = (hdf["Call_OI"].values*hdf["Call_Gamma"].values +
                   hdf["Put_OI"].values*hdf["Put_Gamma"].values)
            sm  = gaussian_filter1d(raw, sigma=SMOOTH_SIGMA)
            sm_n = sm/(sm.max()+1e-9)
            fig.add_trace(go.Scatter(x=hdf["Strike"], y=sm_n,
                name=f"Den@{ht}", line=dict(color=hcols[i%4],width=1,dash="dot"),
                opacity=0.38), row=1, col=1)
        except: pass

    fig.add_trace(go.Scatter(x=df["Strike"], y=df["Convexity"]/(pk+1e-9),
                             name="Convexity (Fast-Move Zone)", fill="tozeroy",
                             fillcolor="rgba(0,200,83,0.12)",
                             line=dict(color=C["convex"],width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Strike"], y=df["GammaDensity"]/(pk+1e-9),
                             name="Gamma Density",
                             line=dict(color=C["density"],width=2.2)), row=1, col=1)

    for lbl,val,col in [("-1σ",an["sig1_lo"],"#c0392b"),("+1σ",an["sig1_hi"],"#27ae60")]:
        _vl(fig,val,lbl,col,dash="dash",row=1,col_n=1)
    for x,lb,cl in [(spot,"Spot",C["spot"]),(an["gamma_peak"],"γPeak",C["gpeak"]),
                    (an["iv_bottom"],"IVBot",C["ivbot"])]:
        lw = 2 if lb=="Spot" else 1.5
        ds = "dash" if lb=="Spot" else ("longdash" if lb=="IVBot" else "dot")
        _vl(fig,x,lb,cl,lw=lw,dash=ds,row=1,col_n=1)

    for lbl,val,col in [("Lower Tail",an["sig1_lo"],"#c0392b"), ("Upper Tail",an["sig1_hi"],"#27ae60")]:
        fig.add_annotation(x=val, y=0.06, text=f"<b>{lbl}</b><br>{val:.0f}",
                            font=dict(color=col,size=9,weight="bold"),
                            bgcolor="white", bordercolor=col,
                            showarrow=True, arrowcolor=col, arrowsize=0.8, row=1, col=1)

    fig.add_trace(go.Bar(x=df["Strike"], y=df["Call_OI"]/1e5, name="Call OI (L)",
                         marker=dict(color=C["cwall"],opacity=0.70), width=38), row=2, col=1)
    fig.add_trace(go.Bar(x=df["Strike"], y=-df["Put_OI"]/1e5, name="Put OI (L)",
                         marker=dict(color=C["pwall"],opacity=0.70), width=38), row=2, col=1)
    fig.add_hline(y=0, line=dict(color="#888",width=1), row=2, col=1)
    for x,lb,cl in [(spot,"Spot",C["spot"]),(an["call_wall"],"CW",C["cwall"]),
                    (an["put_wall"],"PW",C["pwall"]),(an["max_pain"],"Pain",C["maxpain"])]:
        lw = 2 if lb=="Spot" else 1.5
        ds = "dash" if lb=="Spot" else "dot"
        _vl(fig,x,lb,cl,lw=lw,dash=ds,row=2,col_n=1)

    return _apply_theme(fig,
        f"🧲 <b>Gamma Density + OI Structure</b>  |  Peak@{an['gamma_peak']:.0f}  "
        f"IVBot@{an['iv_bottom']:.0f}  ±1σ:{an['sig1_lo']:.0f}–{an['sig1_hi']:.0f}  |  "
        f"GREEN=Fast-Move zone  |  {an['time']}", h=560)

# =============================================================================
# HISTORICAL REPLAY CHART
# =============================================================================
def ch_historical_replay(date_str, time_str):
    if not date_str or not time_str:
        fig = go.Figure()
        fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                           text="Select Date and Time to view historical snapshot",
                           showarrow=False, font=dict(size=14,color="#888"))
        return _apply_theme(fig, "📅 Historical Replay — Select Date & Time", h=520)

    snap_df = load_snapshot(date_str, time_str)
    if snap_df.empty:
        fig = go.Figure()
        fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                           text=f"No snapshot found for {date_str} {time_str}",
                           showarrow=False, font=dict(size=14,color="#888"))
        return _apply_theme(fig, f"📅 Historical {date_str} {time_str} — Not Found", h=520)

    sf  = f"{HISTORY_FOLDER}/daily_summary/summary_{date_str}.csv"
    hdf = pd.read_csv(sf) if os.path.exists(sf) else pd.DataFrame()

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.40,0.32,0.28], vertical_spacing=0.04,
                        subplot_titles=[f"Spot + Key Levels — {date_str} {time_str}",
                                        "Net GEX (Cr)", "ATM IV %"])

    if not hdf.empty:
        t = hdf["time"]
        fig.add_trace(go.Scatter(x=t, y=hdf["spot"], name="Spot",
                                 line=dict(color=C["spot"],width=2.5)), row=1, col=1)
        for col,clr,lbl in [("call_wall",C["cwall"],"CW"), ("put_wall",C["pwall"],"PW"),
                             ("iv_bottom",C["ivbot"],"IVBot"), ("gamma_peak",C["gpeak"],"γPeak"),
                             ("max_pain",C["maxpain"],"Pain")]:
            if col in hdf.columns:
                fig.add_trace(go.Scatter(x=t, y=hdf[col], name=lbl,
                                         line=dict(color=clr,width=1.5,dash="dot")), row=1, col=1)

        sel_rows = hdf[hdf["time"]==time_str]
        if not sel_rows.empty:
            fig.add_vline(x=time_str, line=dict(color="#e63946",width=2,dash="dash"),
                          annotation=dict(text=f"Selected: {time_str}",
                                          font=dict(color="#e63946",weight="bold")), row=1, col=1)

        if "net_gex_cr" in hdf.columns:
            fig.add_trace(go.Bar(x=t, y=hdf["net_gex_cr"], name="Net GEX",
                                 marker_color=["#27ae60" if v>=0 else "#e74c3c"
                                               for v in hdf["net_gex_cr"]], opacity=0.85), row=2, col=1)
            fig.add_hline(y=0, line=dict(color="#888",width=1), row=2, col=1)

        if "atm_iv" in hdf.columns:
            fig.add_trace(go.Scatter(x=t, y=hdf["atm_iv"], name="ATM IV",
                                     line=dict(color="#ff8f00",width=2),
                                     fill="tozeroy", fillcolor="rgba(255,143,0,0.08)"), row=3, col=1)

    fig.update_xaxes(
        rangeselector=dict(
            buttons=[dict(count=30,step="minute",stepmode="backward",label="30m"),
                     dict(count=60,step="minute",stepmode="backward",label="1h"),
                     dict(count=120,step="minute",stepmode="backward",label="2h"),
                     dict(step="all",label="Full Day")],
            bgcolor="#f7f9fc", activecolor="#1565c0", font=dict(size=10,color="#374151")),
        row=1, col=1)

    return _apply_theme(fig,
        f"📅 <b>Historical Replay</b>  |  {date_str}  |  Selected: {time_str}", h=580, dtick=None)

# =============================================================================
# LIVE OPTION CHAIN TABLE
# =============================================================================
def build_chain_html(df, an):
    spot = an["spot"]
    cw1  = an["call_wall"];  pw1 = an["put_wall"]
    ivb  = an["iv_bottom"];  mvs = an["max_vol_s"]
    mcv  = an["max_cv_s"];   mpv = an["max_pv_s"]

    atm_i = int((df["Strike"] - spot).abs().argsort().iloc[0])
    lo    = max(0, atm_i - CHAIN_STRIKES)
    hi    = min(len(df), atm_i + CHAIN_STRIKES + 1)
    sub   = df.iloc[lo:hi].copy().reset_index(drop=True)

    def fmt_oi(v):
        if v >= 1e6: return f"{v/1e6:.2f}M"
        if v >= 1e5: return f"{v/1e5:.1f}L"
        if v >= 1e3: return f"{v/1e3:.0f}K"
        return f"{v:.0f}"

    def fmt_chg(v):
        if v > 500: return f'<span style="color:#155724;font-weight:700">▲{fmt_oi(v)}</span>'
        if v < -500: return f'<span style="color:#721c24;font-weight:700">▼{fmt_oi(abs(v))}</span>'
        return '<span style="color:#888">—</span>'

    def fmt_iv(v):
        return f"{v:.1f}" if v > 0 else "—"

    def row_style(s, is_atm):
        if s == cw1 or s == pw1: return "background:#d4edda;border-left:4px solid #28a745;"
        if s == ivb: return "background:#f8d7da;border-left:4px solid #dc3545;"
        if is_atm: return "background:#cce5ff;border-left:4px solid #004085;"
        if s == mvs: return "background:#fff3cd;border-left:4px solid #856404;font-weight:700;"
        return "background:#ffffff;"

    headline = (f'<div style="padding:6px 12px;background:#1a237e;color:white;'
                f'font-weight:700;font-size:12px;border-radius:8px 8px 0 0;font-family:Inter,Arial;">'
                f'📊 Live Option Chain ±{CHAIN_STRIKES} Strikes &nbsp;|&nbsp; '
                f'★ Max CE Vol: <span style="color:#90caf9">{mcv:.0f}</span> &nbsp;'
                f'★ Max PE Vol: <span style="color:#ffcc80">{mpv:.0f}</span> &nbsp;|&nbsp; '
                f'Max Total Vol: <span style="color:#ffeb3b">{mvs:.0f}</span></div>')

    html = (f'<div style="font-family:Inter,Arial,sans-serif;margin:4px 0;">{headline}'
            f'<div style="overflow-x:auto;border:1px solid #dee2e6;border-radius:0 0 8px 8px;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:11.5px;min-width:900px;">'
            f'<thead>'
            f'<tr style="background:#1a237e;color:white;text-align:center;">'
            f'<th colspan="5" style="padding:7px 4px;border-right:2px solid rgba(255,255,255,0.3);'
            f'color:#90caf9;font-size:11px;">← CALL SIDE</th>'
            f'<th style="padding:7px 8px;background:#0d1757;font-size:12px;font-weight:800;'
            f'min-width:78px;border-left:2px solid rgba(255,255,255,0.3);'
            f'border-right:2px solid rgba(255,255,255,0.3);">STRIKE</th>'
            f'<th colspan="5" style="padding:7px 4px;border-left:2px solid rgba(255,255,255,0.3);'
            f'color:#ffcc80;font-size:11px;">PUT SIDE →</th></tr>'
            f'<tr style="background:#283593;color:#e8eaf6;text-align:center;font-size:10.5px;font-weight:700;">'
            f'<th style="padding:5px 4px;">OI%</th><th style="padding:5px 4px;">OI</th>'
            f'<th style="padding:5px 4px;">IVchg%</th><th style="padding:5px 4px;">IV</th>'
            f'<th style="padding:5px 4px;border-right:2px solid rgba(255,255,255,0.25);">Vol</th>'
            f'<th style="padding:5px 6px;background:#1a237e;"></th>'
            f'<th style="padding:5px 4px;border-left:2px solid rgba(255,255,255,0.25);">Vol</th>'
            f'<th style="padding:5px 4px;">IV</th><th style="padding:5px 4px;">IVchg%</th>'
            f'<th style="padding:5px 4px;">OI</th><th style="padding:5px 4px;">OI%</th>'
            f'</tr></thead><tbody>')

    total_call_oi = sub["Call_OI"].sum()
    total_put_oi  = sub["Put_OI"].sum()

    for _, row in sub.iterrows():
        s      = row["Strike"]
        is_atm = abs(s - spot) < 26
        rs     = row_style(s, is_atm)
        bd     = "border-bottom:1px solid #f0f0f0;"
        cp     = "padding:5px 6px;"
        c_oi_pct = f"{row['Call_OI']/total_call_oi*100:.1f}%" if total_call_oi>0 else "—"
        p_oi_pct = f"{row['Put_OI']/total_put_oi*100:.1f}%"  if total_put_oi >0 else "—"
        sk_bg  = "#0d1757" if is_atm else "#f0f4ff"
        sk_clr = "#ffffff"  if is_atm else "#0d1b4b"
        sk_mk  = "★ " if is_atm else ""
        tags = ""
        if s == cw1: tags += '<span style="background:#28a745;color:white;font-size:8px;padding:1px 3px;border-radius:2px;margin-left:2px;">CW</span>'
        if s == pw1: tags += '<span style="background:#fd7e14;color:white;font-size:8px;padding:1px 3px;border-radius:2px;margin-left:2px;">PW</span>'
        if s == ivb: tags += '<span style="background:#dc3545;color:white;font-size:8px;padding:1px 3px;border-radius:2px;margin-left:2px;">★IV</span>'
        if s == mvs: tags += '<span style="background:#856404;color:white;font-size:8px;padding:1px 3px;border-radius:2px;margin-left:2px;">VOL↑</span>'

        html += (f'<tr style="{rs}{bd}text-align:right;">'
                 f'<td style="{cp}color:#1565c0;font-size:11px;">{c_oi_pct}</td>'
                 f'<td style="{cp}color:#1565c0;font-weight:600;">{fmt_oi(row["Call_OI"])}</td>'
                 f'<td style="{cp}font-size:10px;">{fmt_chg(row["Call_OI_Chg"])}</td>'
                 f'<td style="{cp}color:#1565c0;">{fmt_iv(row["Call_IV"])}</td>'
                 f'<td style="{cp}border-right:2px solid #e0e0e0;color:#546e7a;">{fmt_oi(row["Call_Vol"])}</td>'
                 f'<td style="padding:5px 8px;text-align:center;background:{sk_bg};'
                 f'color:{sk_clr};font-weight:800;font-size:12.5px;'
                 f'border-left:2px solid #e0e0e0;border-right:2px solid #e0e0e0;">'
                 f'{sk_mk}{s:.0f}{tags}</td>'
                 f'<td style="{cp}border-left:2px solid #e0e0e0;color:#546e7a;">{fmt_oi(row["Put_Vol"])}</td>'
                 f'<td style="{cp}color:#c62828;">{fmt_iv(row["Put_IV"])}</td>'
                 f'<td style="{cp}font-size:10px;">{fmt_chg(row["Put_OI_Chg"])}</td>'
                 f'<td style="{cp}color:#c62828;font-weight:600;">{fmt_oi(row["Put_OI"])}</td>'
                 f'<td style="{cp}color:#c62828;font-size:11px;">{p_oi_pct}</td>'
                 f'</tr>')

    legend = (f'</tbody></table></div>'
              f'<div style="margin-top:6px;display:flex;gap:14px;flex-wrap:wrap;align-items:center;'
              f'padding:7px 12px;background:#f8f9fa;border-radius:6px;border:1px solid #e2e8f0;'
              f'font-size:11px;color:#495057;">'
              f'<span><span style="display:inline-block;width:10px;height:10px;background:#d4edda;'
              f'border-left:4px solid #28a745;vertical-align:middle;margin-right:4px;"></span>1st Highest OI (CW/PW)</span>'
              f'<span><span style="display:inline-block;width:10px;height:10px;background:#f8d7da;'
              f'border-left:4px solid #dc3545;vertical-align:middle;margin-right:4px;"></span>★ IV Bottom (Pin Zone)</span>'
              f'<span><span style="display:inline-block;width:10px;height:10px;background:#cce5ff;'
              f'border-left:4px solid #004085;vertical-align:middle;margin-right:4px;"></span>ATM ★</span>'
              f'<span><span style="display:inline-block;width:10px;height:10px;background:#fff3cd;'
              f'border-left:4px solid #856404;vertical-align:middle;margin-right:4px;"></span><b>Max Vol Strike</b></span>'
              f'<span style="margin-left:auto;color:#868e96;font-size:10px;">▲Green=OI Added  ▼Red=OI Shed</span>'
              f'</div></div>')

    return html + legend

# =============================================================================
# SUMMARY BUILDER
# =============================================================================
def build_summary(an, hdf, shifts):
    sep = "═" * 52
    iv_s = gex_s = wall_s = gamma_s = "  (building...)"

    if not hdf.empty and len(hdf) >= 2:
        h = hdf
        if "iv_bottom" in h.columns:
            ip,ic = h["iv_bottom"].iloc[-2], h["iv_bottom"].iloc[-1]
            d = ic-ip
            ar = "⬆" if d>0 else ("⬇" if d<0 else "→")
            flag = "🚨SHIFT!" if abs(d)>100 else "✅OK"
            iv_s = f"  IVBot: {ip:.0f}→{ic:.0f} ({ar}{abs(d):.0f}pts) {flag}"
            if "atm_iv" in h.columns:
                i0,in_ = h["atm_iv"].iloc[0], h["atm_iv"].iloc[-1]
                iv_s += f"\n  ATM IV: {i0:.1f}%→{in_:.1f}% ({'⬆Fear' if in_-i0>0.5 else '⬇Calm' if in_-i0<-0.5 else '→OK'})"
        if "net_gex_cr" in h.columns:
            gp,gc = h["net_gex_cr"].iloc[-2], h["net_gex_cr"].iloc[-1]
            cr = ("  🚨FLIP:Pin→Trend!" if gp>=0>gc else "  🟢FLIP:Trend→Pin!" if gp<0<=gc else "")
            gex_s = f"  GEX: {gp:+.2f}→{gc:+.2f}Cr ({gc-gp:+.2f}){cr}"
        if all(c in h.columns for c in ["call_wall","put_wall"]):
            cp,cc = h["call_wall"].iloc[-2], h["call_wall"].iloc[-1]
            pp,pc = h["put_wall"].iloc[-2],  h["put_wall"].iloc[-1]
            wall_s = (f"  CW: {cp:.0f}→{cc:.0f} ({'⬆Bull' if cc>cp else '⬇Bear' if cc<cp else '→'})\n"
                      f"  PW: {pp:.0f}→{pc:.0f} ({'⬆Bull' if pc>pp else '⬇Bear' if pc<pp else '→'})")
        if "gamma_peak" in h.columns:
            gp2,gc2 = h["gamma_peak"].iloc[-2], h["gamma_peak"].iloc[-1]
            gamma_s = f"  γPeak: {gp2:.0f}→{gc2:.0f}" + (" 🚨MOVED!" if gc2!=gp2 else " ✅Stable")

    if an["net_gex_cr"] >= 0:
        da = f"SELL rallies near {an['call_wall']:.0f} & BUY dips near {an['put_wall']:.0f}"
        ms = "RANGE / PINNING"
    elif an["view"] == "BULLISH":
        da = f"FORCED TO BUY as market rises (Short Gamma) — Amplifies UP moves"
        ms = "TRENDING UP"
    elif an["view"] == "BEARISH":
        da = f"FORCED TO SELL as market falls (Short Gamma) — Amplifies DOWN moves"
        ms = "TRENDING DOWN"
    else:
        da = f"Watching Flip Zones {', '.join(f'{z:.0f}' for z in an['flip_zones'][:2]) or 'N/A'}"
        ms = "UNCERTAIN"

    icon  = {"BULLISH":"🟢","BEARISH":"🔴","NEUTRAL":"⚪"}.get(an["view"],"⚪")
    at    = "\n".join(f"  {a}" for a in an["alerts"])
    st_   = "\n".join(f"  {s}" for s in shifts) if shifts else "  No shifts yet"
    flips = ", ".join(f"{z:.0f}" for z in an["flip_zones"][:3]) or "None"
    vs    = ", ".join(f"{s:.0f}" for s in an["vol_spikes"][:3]) or "—"
    ivs   = ", ".join(f"{s:.0f}" for s in an["iv_spikes"][:3]) or "—"

    return f"""
{sep}
  ⚡ GEX PRO v7.0  |  {an['date']} {an['time']}
{sep}

━━ 1. MARKET STRUCTURE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🏗  Structure : {ms}
  🏹  ±1σ Range : {an['sig1_lo']:.0f} ↔ {an['sig1_hi']:.0f}
  🧱  Call Wall : {an['call_wall']:.0f} ({an['call_1oi']/1e5:.1f}L)  2nd@{an['call_wall2']:.0f}
  🧱  Put  Wall : {an['put_wall']:.0f} ({an['put_1oi']/1e5:.1f}L)   2nd@{an['put_wall2']:.0f}
  🔷  Smart CW  : {an['smart_cw']:.0f}  Smart PW: {an['smart_pw']:.0f}
  🎯  Range     : {an['put_wall']:.0f} — {an['call_wall']:.0f}

━━ 2. POSITIONING & SHIFTS ━━━━━━━━━━━━━━━━━━━━━━━━━━
  🧲  γ Peak    : {an['gamma_peak']:.0f}  (Magnet)
  🎯  IV Bottom★: {an['iv_bottom']:.0f}  (Pin Zone — KEY!)
  😵  Max Pain  : {an['max_pain']:.0f}
  🔀  GEX Flips : {flips}
  🔥  Max Vol @ : {an['max_vol_s']:.0f}  CE:{an['max_cv_s']:.0f}  PE:{an['max_pv_s']:.0f}
  IV Shift:
{iv_s}
  γ Shift:
{gamma_s}
  Wall Shift:
{wall_s}
  GEX Regime:
{gex_s}

━━ 3. PRESSURE & PROBABILITY ━━━━━━━━━━━━━━━━━━━━━━━━
  📊  ATM IV    : {an['atm_iv']:.2f}%   Common IV: {an['common_iv']:.2f}%
  📐  PCR       : {an['pcr']:.3f}
  ⚡  Net GEX   : {an['net_gex_cr']:+.2f} Cr
  🌀  Net Vanna : {an['net_vanna']:+.2f}
  🔥  Vol Spike : {vs}
  ⚡  IV  Spike : {ivs}
  Signals:
{at}

━━ 4. DEALER VIEW ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  {icon}  {an['signal']}  ({an['probability']}% confidence)

  🏦 Dealer FORCED to:
  ╔──────────────────────────────────────────────╗
  ║  {da[:46]}
  ║  Range: {an['put_wall']:.0f} — {an['call_wall']:.0f}
  ║  γ Magnet: {an['gamma_peak']:.0f}   IV Pin: {an['iv_bottom']:.0f}
  ╚──────────────────────────────────────────────╝

━━ 5. ALERTS & SPIKES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{st_}

  Rules: +ve GEX=Range | -ve GEX=Trend
  IV Bottom shift = New direction → Follow it!
  GEX Flip = Most volatile level today
{sep}"""

# =============================================================================
# STREAMLIT UI
# =============================================================================

# ── Header ────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#0d1b4b,#1565c0);
            padding:18px 24px;border-radius:10px;margin-bottom:16px;">
  <h1 style="color:white;margin:0;font-size:24px;font-family:Inter,Arial;font-weight:800;">
    ⚡ GEX PRO v7.0 — Dealer Intelligence Dashboard
  </h1>
  <p style="color:#90caf9;margin:6px 0 0;font-size:13px;">
    Nifty Options · Upstox API · Live Chain · GEX · IV · Vanna · Gamma Density · Historical Replay
  </p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar Controls ──────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Controls")

    token = st.text_input("🔑 Upstox Token", type="password",
                          placeholder="Paste your bearer token here",
                          help="Upstox Developer Console se token copy karo")

    # Load expiries button
    if st.button("📋 Load Expiries", use_container_width=True):
        if not token:
            st.error("Token daalo pehle!")
        else:
            with st.spinner("Expiries load ho rahi hain..."):
                try:
                    h = make_headers(token)
                    exps = get_expiries(h)
                    st.session_state["expiry_list"] = exps
                    st.success(f"✅ {len(exps)} expiries mili!")
                except Exception as e:
                    st.error(f"❌ {e}")

    expiry_list = st.session_state.get("expiry_list", [])
    expiry = st.selectbox("📅 Expiry Date", options=expiry_list,
                          help="Pehle Load Expiries dabaao")

    st.markdown("---")

    # Refresh controls
    col1, col2 = st.columns(2)
    refresh_clicked = col1.button("🔄 Refresh", use_container_width=True, type="primary")
    auto_toggle     = col2.button(
        "⏹ Auto OFF" if st.session_state.auto_on else "⏱ Auto ON",
        use_container_width=True)

    if auto_toggle:
        st.session_state.auto_on = not st.session_state.auto_on
        st.rerun()

    refresh_interval = st.slider("⏰ Auto refresh (seconds)", 30, 300, REFRESH_SEC, 10)

    st.markdown("---")
    if st.session_state.last_refresh:
        st.success(f"✅ Last: {st.session_state.last_refresh}")
    if st.session_state.auto_on:
        st.info(f"⏱ Auto ON — every {refresh_interval}s")
    else:
        st.warning("⏸ Auto OFF")

    st.markdown("---")
    st.markdown("**📁 Data Folder:**")
    st.code(HISTORY_FOLDER, language=None)

# ── Auto refresh logic ────────────────────────────────────────
if st.session_state.auto_on:
    import time as _time
    last = st.session_state.last_refresh
    now_str = datetime.now().strftime("%H:%M:%S")
    should_refresh = (last is None or
                      (datetime.now() - datetime.strptime(last, "%H:%M:%S")
                       ).seconds >= refresh_interval)
    if should_refresh:
        refresh_clicked = True

# ── Main Tabs ─────────────────────────────────────────────────
tab_live, tab_hist, tab_guide = st.tabs(["📊 Live Dashboard", "📅 Historical Replay", "📚 Guide"])

# ══════════════════════════════════════════════════════════════
# TAB 1: LIVE DASHBOARD
# ══════════════════════════════════════════════════════════════
with tab_live:
    if refresh_clicked:
        if not token:
            st.error("⚠️ Pehle sidebar mein Upstox Token daalo!")
        elif not expiry:
            st.error("⚠️ Pehle 'Load Expiries' button dabaao aur expiry select karo!")
        else:
            with st.spinner("🔄 Data fetch ho raha hai..."):
                try:
                    h     = make_headers(token)
                    spot  = get_spot(h)
                    chain = get_chain(expiry, h)
                    res   = compute(chain, spot)
                    df, an= res["df"], res["an"]
                    shifts= detect_shifts(an)
                    hdf   = load_history()
                    save_snap(an, df, expiry, shifts)

                    # Store in session
                    st.session_state["df"]      = df
                    st.session_state["an"]      = an
                    st.session_state["shifts"]  = shifts
                    st.session_state["hdf"]     = hdf
                    st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")

                    if st.session_state.auto_on:
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Error: {e}")

    # Display stored data
    if "an" in st.session_state and st.session_state["an"]:
        df     = st.session_state["df"]
        an     = st.session_state["an"]
        shifts = st.session_state.get("shifts", [])
        hdf    = st.session_state.get("hdf", pd.DataFrame())

        # ── Metric cards row ──────────────────────────────────
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("🏷️ Spot",       f"{an['spot']:.0f}")
        m2.metric("⚡ Net GEX",    f"{an['net_gex_cr']:+.2f} Cr",
                  delta="📌 Pinning" if an['net_gex_cr']>=0 else "💥 Trending")
        m3.metric("📊 ATM IV",     f"{an['atm_iv']:.1f}%")
        m4.metric("📐 PCR",        f"{an['pcr']:.3f}")
        m5.metric("🧱 Call Wall",  f"{an['call_wall']:.0f}")
        m6.metric("🧱 Put Wall",   f"{an['put_wall']:.0f}")

        # ── Signal banner ─────────────────────────────────────
        clr = {"BULLISH":"#d4edda","BEARISH":"#f8d7da","NEUTRAL":"#fff3cd"}.get(an["view"],"#f8f9fa")
        brd = {"BULLISH":"#28a745","BEARISH":"#dc3545","NEUTRAL":"#856404"}.get(an["view"],"#6c757d")
        st.markdown(f"""
        <div style="padding:12px 18px;background:{clr};border-left:5px solid {brd};
                    border-radius:6px;margin:10px 0;font-family:Inter,Arial;">
          <b style="font-size:16px;">{an['signal']}</b>
          &nbsp;&nbsp;|&nbsp;&nbsp; Confidence: <b>{an['probability']}%</b>
          &nbsp;&nbsp;|&nbsp;&nbsp; IV Bottom★: <b>{an['iv_bottom']:.0f}</b>
          &nbsp;&nbsp;|&nbsp;&nbsp; γ Peak: <b>{an['gamma_peak']:.0f}</b>
          &nbsp;&nbsp;|&nbsp;&nbsp; Max Pain: <b>{an['max_pain']:.0f}</b>
          &nbsp;&nbsp;|&nbsp;&nbsp; ±1σ: <b>{an['sig1_lo']:.0f} ↔ {an['sig1_hi']:.0f}</b>
        </div>""", unsafe_allow_html=True)

        # ── Main layout: Charts left | Summary right ──────────
        col_charts, col_summary = st.columns([3, 1])

        with col_charts:
            # Option Chain Table
            st.markdown("### 📋 Live Option Chain")
            st.markdown(build_chain_html(df, an), unsafe_allow_html=True)
            st.markdown("---")

            # Charts
            st.plotly_chart(ch_gex_oi(df, an),     use_container_width=True)
            st.plotly_chart(ch_iv(df, an),          use_container_width=True)
            st.plotly_chart(ch_density_oi(df, an),  use_container_width=True)

        with col_summary:
            summary_text = build_summary(an, hdf, shifts)
            st.markdown("### 📋 Summary")
            st.text_area("", value=summary_text, height=1400, label_visibility="collapsed")

            if shifts:
                st.markdown("### 🚨 Live Shifts")
                for s in shifts:
                    st.warning(s)

    else:
        st.info("👈 Left sidebar mein Token daalo → Expiries load karo → 🔄 Refresh dabaao")
        st.markdown("""
        <div style="padding:20px;background:#f0f4ff;border-radius:10px;font-family:Inter,Arial;">
        <h3>🚀 Quick Start Guide</h3>
        <ol>
          <li><b>Upstox token</b> sidebar mein paste karo</li>
          <li><b>📋 Load Expiries</b> button dabaao</li>
          <li>Dropdown se <b>expiry date</b> select karo</li>
          <li><b>🔄 Refresh</b> dabaao — data load hoga!</li>
          <li><b>⏱ Auto ON</b> karo — har 60 seconds mein khud refresh hoga</li>
        </ol>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 2: HISTORICAL REPLAY
# ══════════════════════════════════════════════════════════════
with tab_hist:
    st.markdown("### 📅 Historical Replay")
    available_dates = get_available_dates()

    if not available_dates:
        st.info("📭 Abhi koi historical data nahi hai. Pehle Live Dashboard se data collect karo.")
    else:
        hc1, hc2, hc3 = st.columns([2, 2, 1])
        sel_date = hc1.selectbox("📆 Date Select karo", available_dates,
                                  index=len(available_dates)-1)
        times_for_date = get_snapshots_for_date(sel_date)
        sel_time = hc2.selectbox("🕐 Time Select karo", times_for_date,
                                  index=len(times_for_date)-1 if times_for_date else 0)
        load_snap_btn = hc3.button("▶ Load", type="primary", use_container_width=True)

        if load_snap_btn or (sel_date and sel_time):
            st.plotly_chart(ch_historical_replay(sel_date, sel_time), use_container_width=True)

# ══════════════════════════════════════════════════════════════
# TAB 3: GUIDE
# ══════════════════════════════════════════════════════════════
with tab_guide:
    st.markdown("""
# 📚 GEX PRO v7.0 — Complete Guide

---

## 🚀 60 Seconds mein kaise use karein

1. **Auto ON** button dabaao (left sidebar)
2. **Summary Part 1** dekho — Range hai ya Trend?
3. **Part 2** — IV Bottom★ shift ho raha hai? **(SABSE IMPORTANT)**
4. **Part 3** — GEX +ve=Pin | -ve=Trend
5. **Part 4** — Dealer ko kya karna MAJBOOR hai?
6. **Part 5** — Koi Volume/IV spike hai?

---

## 📊 Live Option Chain Table

- ±15 strikes ATM ke around dikhata hai
- Columns: `OI%  |  OI  |  IVchg%  |  IV  |  Vol  ||  STRIKE  ||  Vol  |  IV  |  IVchg%  |  OI  |  OI%`
- 🟩 **Green row** = 1st Highest OI (Call Wall / Put Wall)
- 🟥 **Red row** = IV Bottom ★ (Expected pin/expiry strike)
- 🟦 **Blue row** = ATM strike ★
- 🟨 **Yellow row** = Max Volume strike (smart money active)

---

## 📈 Chart 1: GEX + OI Structure

**Top half:** GEX Exposure (Buy=Green, Sell=Red, Neutral=Grey)
**Bottom half:** OI Density (Call↑ Blue, Put↓ Orange)

| Condition | Matlab |
|-----------|--------|
| GEX +ve | Range/Pin day → Dealers sell rallies, buy dips |
| GEX -ve | Trending day → Dealers amplify direction |
| GEX Flip Zone | Jahan Net GEX=0 → Sabse volatile level |
| Call Wall | Max Call OI → Resistance |
| Put Wall | Max Put OI → Support |

---

## 📉 Chart 2: IV Chart (±10 Strikes)

- **Purple dashed** = Common IV (baseline)
- **★ Star** = ATM IV
- **▼ Triangle** = IV Bottom (lowest IV strike = PIN ZONE)

| IV Bottom | Matlab |
|-----------|--------|
| UP shift | Market drift UP karega |
| DOWN shift | Market drift DOWN karega |
| Spot ke paas | Expiry pin expected here |

---

## 🧲 Chart 3: Gamma Density + OI

- **Green fill** = Convexity Zone (fast moves yahaan hote hain)
- **Gamma Peak** = Strongest magnetic level (spot yahaan attract hota hai)
- **±1σ lines** = Daily expected range

---

## 🔑 Key Rules

```
+ve Net GEX  → Range day    → Dealers sell rallies, buy dips
-ve Net GEX  → Trend day    → Dealers amplify moves
GEX Flip Zone → Gamma=0 level → Sabse volatile strike
IV Bottom ★   → Expected expiry pin (SABSE IMPORTANT level!)
IV Bottom shift → Follow karo for direction
Gamma Peak    → Magnetic pull — spot yahaan aata hai
PCR > 1.3     → Bullish positioning
PCR < 0.7     → Bearish positioning
Vanna +ve     → IV rise = Dealers BUY (bullish)
Vanna -ve     → IV rise = Dealers SELL (bearish)
```

---

## 📋 Common Scenarios

**SCENARIO A — Strong Pin Day:**
+ve GEX, IV Bottom near spot, Gamma Peak near spot
→ Options becho, range-bound strategy

**SCENARIO B — Trending Breakout:**
-ve GEX, IV Bottom door from spot, GEX Flip crossed
→ Directional play, IV Bottom ka direction follow karo

**SCENARIO C — GEX Flip Imminent:**
GEX near 0, spot approaching Flip Zone
→ Options mat becho, volatile move expect karo

**SCENARIO D — Call Wall Resistance:**
Spot near Call Wall, PCR girta hua, +ve Skew
→ Rally se dur raho, puts buy karo / CE spreads becho

**SCENARIO E — Put Wall Support:**
Spot near Put Wall, PCR badhta hua, -ve Skew
→ Dip buy karo, calls buy karo / PE spreads becho

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| Token error | Upstox console se fresh token copy karo |
| No expiries | Token sahi hai? Load Expiries dobara dabaao |
| Charts blank | Network check karo, NSE market hours mein try karo |
| App band ho jaaye | Terminal mein wahi command dobara run karo |
""")

# ── Auto-refresh rerun ────────────────────────────────────────
if st.session_state.auto_on:
    time.sleep(refresh_interval)
    st.rerun()
