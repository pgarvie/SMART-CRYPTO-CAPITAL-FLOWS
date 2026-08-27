"""
SYSTEM PLEXIS CRYPTO v1.0 - REAL-TIME CRYPTO CAPITAL ROTATION
Opérateur : Philippe Garvie
Source     : CryptoBubbles API (TOP ~1000 actifs)
Dashboard  : 4 panneaux — Freeze Frame (gauche) | Live (droite)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import json
import os
import time
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION PAGE  (1er appel Streamlit obligatoire)
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="PLEXIS CRYPTO v1.0 — Rotation Capital",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

DATA_URL         = "https://cryptobubbles.net/backend/data/bubbles1000.usd.json"
DATA_FILE        = "data/crypto_snapshot.json"
DEFAULT_INTERVAL = 300   # secondes

INTERVALS = {
    "5 min  — Scalping":         5,
    "15 min — Day Trading actif": 15,
    "30 min — Day Trading modéré": 30,
    "1 h    — Intra-Swing":      60,
    "3 h    — Swing Standard":   180,
    "6 h    — Swing Basse Fréq": 360,
    "12 h   — Macro-Swing":      720,
    "24 h   — Position Trading": 1440,
}

# ══════════════════════════════════════════════════════════════════════════════
# CSS  (même charte visuelle que PLEXIS Sectoriel)
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    .panel-title {
        font-family: monospace;
        font-size: 0.80rem;
        color: #888;
        letter-spacing: 2px;
        text-transform: uppercase;
        border-bottom: 1px solid #333;
        padding-bottom: 4px;
        margin-bottom: 10px;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 4px;
        font-weight: bold;
        font-family: monospace;
        font-size: 0.88rem;
    }
    .divider { border-top: 1px solid #2a2d35; margin: 12px 0; }
    div[data-testid="column"]  { padding: 0 8px; }
    div[data-testid="stMetric"] {
        background: #1a1d23;
        border-radius: 8px;
        padding: 8px 12px;
    }
    .suspects-box {
        background: #1a1d23;
        border-radius: 8px;
        padding: 10px 14px;
        border-left: 3px solid #ffd600;
        font-family: monospace;
        font-size: 0.78rem;
        color: #ccc;
        margin-top: 8px;
    }
    .coverage-note {
        font-family: monospace;
        font-size: 0.72rem;
        color: #555;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS MÉTIER
# ══════════════════════════════════════════════════════════════════════════════

def fetch_cryptobubbles() -> tuple[pd.DataFrame | None, datetime | None]:
    """Télécharge et aplatit les données CryptoBubbles (~1000 actifs)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (PLEXIS-Crypto/1.0)"}
        resp = requests.get(DATA_URL, timeout=15, headers=headers)
        resp.raise_for_status()
        raw = resp.json()

        records = []
        for crypto in raw:
            rec = {}
            for k, v in crypto.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        rec[f"{k}_{sk}"] = sv
                else:
                    rec[k] = v
            records.append(rec)

        df = pd.DataFrame(records)
        for col in ["marketcap", "price", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df, datetime.now()

    except Exception as e:
        st.error(f"❌ Erreur CryptoBubbles : {e}")
        return None, None


def analyze_flows(df_t1: pd.DataFrame, df_t2: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule la variation de market cap (proxy du flux de capital)
    entre deux snapshots.
    Retourne le DataFrame fusionné trié par Delta_MarketCap décroissant.
    """
    key = "name" if "name" in df_t1.columns else "symbol"

    merged = df_t1.merge(df_t2, on=key, suffixes=("_T1", "_T2"), how="inner")
    merged["Delta_MC"]       = merged["marketcap_T2"] - merged["marketcap_T1"]
    merged["Price_Chg_Pct"]  = (
        (merged["price_T2"] - merged["price_T1"]) / merged["price_T1"] * 100
    ).round(2)

    if "volume_T1" in merged.columns and "volume_T2" in merged.columns:
        merged["Vol_Chg_Pct"] = (
            (merged["volume_T2"] - merged["volume_T1"]) / merged["volume_T1"] * 100
        ).round(2)
    else:
        merged["Vol_Chg_Pct"] = np.nan

    merged["Flux_M"]  = (merged["Delta_MC"] / 1_000_000).round(2)
    merged["name_col"] = merged[key]

    return merged.sort_values("Delta_MC", ascending=False).reset_index(drop=True)


def compute_macro_crypto(df: pd.DataFrame, n_scanned: int) -> dict:
    """Calcule les métriques macro sur l'ensemble des actifs scannés."""
    total_flow  = float(df["Flux_M"].sum())
    inflow      = float(df[df["Flux_M"] > 0]["Flux_M"].sum())
    outflow     = float(df[df["Flux_M"] < 0]["Flux_M"].sum())
    n_positive  = int((df["Flux_M"] > 0).sum())
    n_negative  = int((df["Flux_M"] < 0).sum())
    health      = round(inflow / abs(outflow), 2) if outflow != 0 else 1.0

    if health > 1.5:
        status = "🟢 ACCRÉTION MASSIVE (Risk-On)"
        color  = "#00c853"
    elif health > 0.8:
        status = "🟡 ÉQUILIBRE (Rotation en cours)"
        color  = "#ffd600"
    else:
        status = "🔴 DÉLESTAGE GÉNÉRALISÉ (Risk-Off)"
        color  = "#ff1744"

    # Suspects
    suspects_dist = df[
        (df["Price_Chg_Pct"] < -2) & (df["Vol_Chg_Pct"] > 20)
    ][["name_col", "Price_Chg_Pct", "Vol_Chg_Pct"]].head(5).to_dict("records")

    suspects_pump = df[
        (df["Price_Chg_Pct"] > 5) & (df["Vol_Chg_Pct"] < -30)
    ][["name_col", "Price_Chg_Pct", "Vol_Chg_Pct"]].head(5).to_dict("records")

    return {
        "total_flow":     round(total_flow, 2),
        "inflow":         round(inflow, 2),
        "outflow":        round(outflow, 2),
        "n_positive":     n_positive,
        "n_negative":     n_negative,
        "n_scanned":      n_scanned,
        "health":         health,
        "status":         status,
        "status_color":   color,
        "suspects_dist":  suspects_dist,
        "suspects_pump":  suspects_pump,
    }


def save_freeze(df: pd.DataFrame, macro: dict, label: str, t1: str, t2: str,
                interval_name: str, mode: str) -> None:
    """Persiste le freeze frame dans data/crypto_snapshot.json."""
    os.makedirs("data", exist_ok=True)
    payload = {
        "label":         label,
        "t1":            t1,
        "t2":            t2,
        "interval_name": interval_name,
        "mode":          mode,
        "flows":         df.to_dict(orient="records"),
        "macro":         macro,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_freeze() -> dict | None:
    """Charge le dernier freeze frame persisté."""
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES PLOTLY
# ══════════════════════════════════════════════════════════════════════════════

def make_top10_charts(df: pd.DataFrame, title_prefix: str, panel_id: str) -> None:
    """
    Affiche côte à côte :
      - TOP 10 INFLOWS  (vert)
      - TOP 10 OUTFLOWS (rouge)
    Chaque chart reçoit une key unique basée sur panel_id.
    """
    top_in  = df.nlargest(10,  "Flux_M").copy()
    top_out = df.nsmallest(10, "Flux_M").copy()

    col_in, col_out = st.columns(2)

    # ── TOP 10 INFLOWS ────────────────────────────────────────────────────────
    with col_in:
        fig_in = go.Figure(go.Bar(
            x=top_in["Flux_M"],
            y=top_in["name_col"],
            orientation="h",
            marker_color="#00c853",
            text=[f"+{v:.1f}M$" for v in top_in["Flux_M"]],
            textposition="outside",
            textfont=dict(size=9, color="#ccc"),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Inflow : +%{x:.2f} M$<br>"
                "Prix : %{customdata[0]:+.2f}%"
                "<extra></extra>"
            ),
            customdata=top_in[["Price_Chg_Pct"]].values,
        ))
        fig_in.update_layout(
            title=dict(
                text=f"🟢 TOP 10 INFLOWS — {title_prefix}",
                font=dict(size=11, color="#00c853"), x=0.01,
            ),
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font=dict(color="#ccc", family="monospace"),
            xaxis=dict(title="Flux Entrants (M$)", gridcolor="#2a2d35",
                       zerolinecolor="#555", zerolinewidth=1.5),
            yaxis=dict(gridcolor="#1a1d23", autorange="reversed"),
            margin=dict(l=10, r=70, t=40, b=30),
            height=360,
        )
        st.plotly_chart(fig_in, use_container_width=True,
                        key=f"inflow_{panel_id}")

    # ── TOP 10 OUTFLOWS ───────────────────────────────────────────────────────
    with col_out:
        fig_out = go.Figure(go.Bar(
            x=top_out["Flux_M"],
            y=top_out["name_col"],
            orientation="h",
            marker_color="#ff1744",
            text=[f"{v:.1f}M$" for v in top_out["Flux_M"]],
            textposition="outside",
            textfont=dict(size=9, color="#ccc"),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Outflow : %{x:.2f} M$<br>"
                "Prix : %{customdata[0]:+.2f}%"
                "<extra></extra>"
            ),
            customdata=top_out[["Price_Chg_Pct"]].values,
        ))
        fig_out.update_layout(
            title=dict(
                text=f"🔴 TOP 10 OUTFLOWS — {title_prefix}",
                font=dict(size=11, color="#ff1744"), x=0.01,
            ),
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font=dict(color="#ccc", family="monospace"),
            xaxis=dict(title="Flux Sortants (M$)", gridcolor="#2a2d35",
                       zerolinecolor="#555", zerolinewidth=1.5),
            yaxis=dict(gridcolor="#1a1d23", autorange="reversed"),
            margin=dict(l=10, r=70, t=40, b=30),
            height=360,
        )
        st.plotly_chart(fig_out, use_container_width=True,
                        key=f"outflow_{panel_id}")


def make_balance_chart(macro: dict, title: str, panel_id: str) -> None:
    """Graphique Inflow vs Outflow global."""
    fig = go.Figure(go.Bar(
        x=["Pression Acheteuse", "Pression Vendeuse"],
        y=[macro["inflow"], abs(macro["outflow"])],
        marker_color=["#00c853", "#ff1744"],
        text=[f"{macro['inflow']:,.0f}M$", f"{abs(macro['outflow']):,.0f}M$"],
        textposition="outside",
        textfont=dict(size=11, color="#ccc"),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=11, color="#ccc"), x=0.01),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#ccc", family="monospace"),
        yaxis=dict(title="Millions $", gridcolor="#2a2d35"),
        xaxis=dict(gridcolor="#1a1d23"),
        margin=dict(l=10, r=20, t=40, b=20),
        height=240,
    )
    st.plotly_chart(fig, use_container_width=True,
                    key=f"balance_{panel_id}")


# ══════════════════════════════════════════════════════════════════════════════
# RENDU PANNEAU MACRO COMPLET
# ══════════════════════════════════════════════════════════════════════════════

def render_macro_panel(macro: dict, t1: str, t2: str,
                       interval_name: str, mode: str, panel_id: str) -> None:
    """
    Panneau bas : métriques macro + suspects + graphique balance.
    panel_id garantit l'unicité de toutes les keys Streamlit.
    """
    # Badge de statut
    st.markdown(
        f'<span class="status-badge" '
        f'style="background:{macro["status_color"]}22;'
        f'color:{macro["status_color"]};'
        f'border:1px solid {macro["status_color"]};">'
        f'{macro["status"]}</span>',
        unsafe_allow_html=True,
    )

    # Note de couverture
    st.markdown(
        f'<div class="coverage-note">'
        f'📡 Univers analysé : <b>{macro["n_scanned"]} actifs</b> scannés '
        f'(source CryptoBubbles TOP ~1000) — '
        f'Intervalle : <b>{interval_name}</b> — Mode : <b>{mode}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Métriques
    ca, cb = st.columns(2)
    ca.metric("🟢 Inflow Total",  f"{macro['inflow']:,.1f} M$")
    cb.metric("🔴 Outflow Total", f"{abs(macro['outflow']):,.1f} M$")

    cc, cd, ce, cf = st.columns(4)
    cc.metric("Flux Net",          f"{macro['total_flow']:+,.1f} M$")
    cd.metric("Actifs en hausse",  f"{macro['n_positive']}/{macro['n_scanned']}")
    ce.metric("Actifs en baisse",  f"{macro['n_negative']}/{macro['n_scanned']}")
    cf.metric("Score Santé",       f"{macro['health']:.2f}")

    # Graphique balance
    make_balance_chart(
        macro,
        f"Équilibre Inflow/Outflow — {t1} → {t2}",
        panel_id,
    )

    # Mouvements suspects
    has_dist = len(macro.get("suspects_dist", [])) > 0
    has_pump = len(macro.get("suspects_pump", [])) > 0

    if has_dist or has_pump:
        st.markdown(
            "<div class='panel-title'>⚠️ Mouvements suspects</div>",
            unsafe_allow_html=True,
        )
        if has_dist:
            lines = "\n".join([
                f"  🚨 {r['name_col']:<28}  "
                f"Prix {r['Price_Chg_Pct']:+.2f}%  "
                f"Vol {r['Vol_Chg_Pct']:+.2f}%"
                for r in macro["suspects_dist"]
            ])
            st.markdown(
                f'<div class="suspects-box">'
                f'<b>DISTRIBUTION POSSIBLE (Prix↓ + Volume↑)</b><br>'
                f'<pre style="margin:4px 0 0 0; color:#ffd600;">{lines}</pre>'
                f'</div>',
                unsafe_allow_html=True,
            )
        if has_pump:
            lines = "\n".join([
                f"  🎭 {r['name_col']:<28}  "
                f"Prix {r['Price_Chg_Pct']:+.2f}%  "
                f"Vol {r['Vol_Chg_Pct']:+.2f}%"
                for r in macro["suspects_pump"]
            ])
            st.markdown(
                f'<div class="suspects-box" style="border-left-color:#ff1744;">'
                f'<b>PUMP SUSPECT (Prix↑ + Volume↓)</b><br>'
                f'<pre style="margin:4px 0 0 0; color:#ff7043;">{lines}</pre>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE — INITIALISATION
# ══════════════════════════════════════════════════════════════════════════════

defaults = {
    # Live
    "live_df":          None,
    "live_macro":       None,
    "live_t1":          None,   # timestamp string du snapshot de référence
    "live_t2":          None,   # timestamp string du dernier fetch
    "live_df_ref":      None,   # DataFrame snapshot T1 (référence pour mode cumulatif)
    "live_ts_ref":      None,   # datetime objet du T1
    # Freeze frame
    "freeze_df":        None,
    "freeze_macro":     None,
    "freeze_label":     None,
    "freeze_t1":        None,
    "freeze_t2":        None,
    "freeze_interval":  None,
    "freeze_mode":      None,
    # Contrôle
    "last_refresh":     0.0,
    "cycle_count":      0,
    "interval_name":    "5 min  — Scalping",
    "mode":             "Évolutif (vs précédent)",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Chargement du freeze persisté au démarrage
if st.session_state.freeze_df is None:
    saved = load_freeze()
    if saved:
        st.session_state.freeze_df       = pd.DataFrame(saved["flows"])
        st.session_state.freeze_macro    = saved["macro"]
        st.session_state.freeze_label    = saved["label"]
        st.session_state.freeze_t1       = saved["t1"]
        st.session_state.freeze_t2       = saved["t2"]
        st.session_state.freeze_interval = saved["interval_name"]
        st.session_state.freeze_mode     = saved["mode"]


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ PLEXIS CRYPTO Controls")
    st.markdown("---")

    # Intervalle de monitoring
    interval_name = st.selectbox(
        "⏱ Intervalle de monitoring",
        list(INTERVALS.keys()),
        index=list(INTERVALS.keys()).index(st.session_state.interval_name),
    )
    st.session_state.interval_name = interval_name
    interval_minutes = INTERVALS[interval_name]
    refresh_seconds  = interval_minutes * 60

    # Mode d'analyse
    mode = st.radio(
        "📈 Mode d'analyse",
        ["Évolutif (vs précédent)", "Cumulatif (vs snapshot initial)"],
        index=0 if st.session_state.mode == "Évolutif (vs précédent)" else 1,
    )
    st.session_state.mode = mode

    st.markdown("---")

    if st.button("🔄 Rafraîchir maintenant", use_container_width=True):
        st.session_state.last_refresh = 0.0

    if st.button("🔁 Réinitialiser T1 (nouveau snapshot de référence)",
                 use_container_width=True):
        st.session_state.live_df_ref  = None
        st.session_state.live_ts_ref  = None
        st.session_state.live_df      = None
        st.session_state.live_macro   = None
        st.session_state.cycle_count  = 0
        st.session_state.last_refresh = 0.0
        st.success("✅ T1 réinitialisé — nouveau cycle au prochain fetch.")

    st.markdown("---")
    st.markdown("### 📸 Freeze Frame")
    st.caption(
        "Fige une copie du panneau LIVE à gauche "
        "pour comparaison ultérieure."
    )

    freeze_label = st.text_input("🏷 Label du freeze", value="Snapshot Manuel")

    if st.button("📸 Freeze le panneau LIVE", use_container_width=True,
                 type="primary"):
        if st.session_state.live_df is not None:
            st.session_state.freeze_df       = st.session_state.live_df.copy()
            st.session_state.freeze_macro    = st.session_state.live_macro.copy()
            st.session_state.freeze_label    = freeze_label
            st.session_state.freeze_t1       = st.session_state.live_t1
            st.session_state.freeze_t2       = st.session_state.live_t2
            st.session_state.freeze_interval = st.session_state.interval_name
            st.session_state.freeze_mode     = st.session_state.mode
            save_freeze(
                st.session_state.freeze_df,
                st.session_state.freeze_macro,
                freeze_label,
                st.session_state.live_t1,
                st.session_state.live_t2,
                st.session_state.interval_name,
                st.session_state.mode,
            )
            st.success(f"✅ Freeze '{freeze_label}' sauvegardé !")
        else:
            st.warning("⚠️ Aucune donnée live à figer.")

    st.markdown("---")
    st.caption("PLEXIS CRYPTO v1.0 · Philippe Garvie")
    st.caption(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if st.session_state.cycle_count > 0:
        st.caption(f"🔄 Cycles complétés : {st.session_state.cycle_count}")


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-REFRESH — LOGIQUE DE FETCH
# ══════════════════════════════════════════════════════════════════════════════

now_ts = time.time()
time_since = now_ts - st.session_state.last_refresh
cumulative = (st.session_state.mode == "Cumulatif (vs snapshot initial)")

if time_since >= refresh_seconds:
    with st.spinner("📡 Connexion à CryptoBubbles..."):
        df_new, ts_new = fetch_cryptobubbles()

    if df_new is not None:
        # Premier fetch → on établit T1
        if st.session_state.live_df_ref is None:
            st.session_state.live_df_ref = df_new
            st.session_state.live_ts_ref = ts_new
            st.session_state.live_t1     = ts_new.strftime("%d/%m/%Y %H:%M")
            st.session_state.last_refresh = now_ts
            st.info(
                f"📡 Snapshot T1 établi à "
                f"{st.session_state.live_t1} — "
                f"{len(df_new)} actifs chargés. "
                f"Prochain fetch dans {interval_minutes} min."
            )
        else:
            # Fetch suivant → calcul des flux
            if cumulative:
                df_ref = st.session_state.live_df_ref
                t1_str = st.session_state.live_ts_ref.strftime("%d/%m/%Y %H:%M")
            else:
                # Mode évolutif : T1 = dernier snapshot stocké dans live_df
                # On a besoin du raw dataframe T1 précédent
                df_ref = st.session_state.get("live_df_raw_prev",
                                               st.session_state.live_df_ref)
                t1_str = st.session_state.live_t1

            df_merged = analyze_flows(df_ref, df_new)
            t2_str    = ts_new.strftime("%d/%m/%Y %H:%M")

            st.session_state.live_df      = df_merged
            st.session_state.live_macro   = compute_macro_crypto(
                df_merged, len(df_merged)
            )
            st.session_state.live_t1      = t1_str
            st.session_state.live_t2      = t2_str
            st.session_state.cycle_count += 1
            st.session_state.last_refresh = now_ts

            # Sauvegarder le raw pour le prochain cycle évolutif
            st.session_state["live_df_raw_prev"] = df_new


# ══════════════════════════════════════════════════════════════════════════════
# EN-TÊTE
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(
    "<h2 style='font-family:monospace; letter-spacing:3px; color:#00c853;'>"
    "₿ PLEXIS CRYPTO v1.0 — ROTATION DU CAPITAL</h2>",
    unsafe_allow_html=True,
)
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT PRINCIPAL — 4 PANNEAUX
# ══════════════════════════════════════════════════════════════════════════════

col_left, col_sep, col_right = st.columns([10, 0.3, 10])

# ─────────────────────────────────────────────────────────────────────────────
# COLONNE GAUCHE — Freeze Frame
# ─────────────────────────────────────────────────────────────────────────────

with col_left:

    flabel = st.session_state.freeze_label or "—"
    ft1    = st.session_state.freeze_t1    or "—"
    ft2    = st.session_state.freeze_t2    or "—"
    finter = st.session_state.freeze_interval or "—"
    fmode  = st.session_state.freeze_mode  or "—"

    # PANNEAU HAUT-GAUCHE
    st.markdown(
        f"<div class='panel-title'>"
        f"📸 Freeze Frame — {flabel} &nbsp;|&nbsp; {ft1} → {ft2}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.freeze_df is not None:
        make_top10_charts(
            st.session_state.freeze_df,
            f"{flabel} ({finter})",
            panel_id="frozen",
        )
    else:
        st.info(
            "Aucun freeze frame. Cliquez sur "
            "**📸 Freeze le panneau LIVE** dans la sidebar."
        )

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # PANNEAU BAS-GAUCHE
    st.markdown(
        "<div class='panel-title'>📊 Analyse Macro — Freeze Frame</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.freeze_macro is not None:
        render_macro_panel(
            st.session_state.freeze_macro,
            ft1, ft2, finter, fmode,
            panel_id="frozen",
        )
    else:
        st.caption("En attente du premier freeze frame...")


# ─────────────────────────────────────────────────────────────────────────────
# SÉPARATEUR
# ─────────────────────────────────────────────────────────────────────────────

with col_sep:
    st.markdown(
        "<div style='border-left:1px solid #2a2d35;"
        "height:1100px; margin:0 auto;'></div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# COLONNE DROITE — Live
# ─────────────────────────────────────────────────────────────────────────────

with col_right:

    lt1  = st.session_state.live_t1 or "En attente T1..."
    lt2  = st.session_state.live_t2 or "—"
    next_r = max(
        0,
        int(refresh_seconds - (time.time() - st.session_state.last_refresh))
    )

    # PANNEAU HAUT-DROIT
    st.markdown(
        f"<div class='panel-title'>"
        f"🔴 Live — {lt1} → {lt2} &nbsp;|&nbsp; "
        f"<span style='color:#555;'>Prochain fetch dans {next_r}s</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.live_df is not None:
        make_top10_charts(
            st.session_state.live_df,
            f"{st.session_state.interval_name} · {st.session_state.mode[:3].upper()}",
            panel_id="live",
        )
    elif st.session_state.live_df_ref is not None:
        st.info(
            f"⏳ T1 établi à **{lt1}** ({len(st.session_state.live_df_ref)} actifs). "
            f"Premier calcul de flux dans **{next_r}s**..."
        )
    else:
        st.info("⏳ Connexion à CryptoBubbles en cours...")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # PANNEAU BAS-DROIT
    st.markdown(
        "<div class='panel-title'>📊 Analyse Macro — Séance Live</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.live_macro is not None:
        render_macro_panel(
            st.session_state.live_macro,
            lt1, lt2,
            st.session_state.interval_name,
            st.session_state.mode,
            panel_id="live",
        )
    else:
        st.caption(
            "En attente du premier cycle complet "
            f"(T1 + {interval_minutes} min)..."
        )


# ══════════════════════════════════════════════════════════════════════════════
# BOUCLE DE POLLING
# ══════════════════════════════════════════════════════════════════════════════

time.sleep(5)
st.rerun()
