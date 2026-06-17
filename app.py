import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re
import requests
import base64
from datetime import datetime
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KOLs Spending Dashboard 2026",
    page_icon="📊",
    layout="wide",
)

# ── Mantle brand palette ──────────────────────────────────────────────────────
# Background: #F5F7F2 (light), Cards: #FFFFFF
# Primary text: #0B2618 (dark forest green)
# Accent: #3DFFA0 (mint green)
# Secondary: #1A4A2E
# Border: #D4E6DA

st.markdown("""
<style>
  /* Hide Streamlit top bar / hamburger */
  #MainMenu { visibility: hidden; }
  header[data-testid="stHeader"] { background: transparent; height: 0; }
  footer { visibility: hidden; }

  /* Global */
  .stApp { background-color: #F5F7F2; }
  .block-container { padding-top: 2.5rem; max-width: 1400px; }
  h1, h2, h3 { color: #0B2618 !important; }
  h1 { font-size: 1.7rem !important; margin-bottom: 0 !important; font-weight: 800 !important; }
  h3 { font-size: 1.05rem !important; margin-bottom: 8px !important; }
  p, label, .stMarkdown { color: #0B2618; }

  /* Sidebar */
  [data-testid="stSidebar"] { background-color: #0B2618 !important; }
  [data-testid="stSidebar"] * { color: #F5F7F2 !important; }
  [data-testid="stSidebar"] h1 { color: #3DFFA0 !important; font-size: 1.1rem !important; }
  [data-testid="stSidebar"] .stRadio label { color: #F5F7F2 !important; }
  [data-testid="stSidebar"] .stButton button {
    background: #3DFFA0; color: #0B2618; border: none;
    font-weight: 700; border-radius: 8px; width: 100%;
  }

  /* Info pill — MNT price */
  .pill {
    display: flex; align-items: flex-start; flex-direction: column; gap: 2px;
    background: #FFFFFF; border: 1.5px solid #3DFFA0; border-radius: 10px;
    padding: 7px 14px; font-size: 12px; color: #0B2618;
    box-shadow: 0 1px 4px rgba(11,38,24,0.08); width: 100%; box-sizing: border-box;
  }
  .pill .pill-label { color: #4A7A5A; font-size: 11px; }
  .pill .pill-val   { color: #0B2618; font-size: 15px; font-weight: 800; }
  .pill .pill-src   { color: #7A9A8A; font-size: 10px; }

  /* Info pill — data notice */
  .info-pill {
    background: #FFFFFF; border: 1.5px solid #D4E6DA; border-radius: 10px;
    padding: 7px 14px; font-size: 11px; color: #4A7A5A; line-height: 1.6;
    box-shadow: 0 1px 4px rgba(11,38,24,0.06);
  }
  .info-pill b { color: #0B2618; }

  /* Total spend box */
  .total-box {
    background: #0B2618; border-radius: 16px;
    padding: 22px 24px; height: 100%;
  }
  .total-box .total-label { font-size: 12px; color: #7AB89A; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .5px; }
  .total-box .total-val   { font-size: 36px; font-weight: 900; color: #3DFFA0; margin-bottom: 18px; }
  .cur-row  { display: flex; gap: 8px; }
  .cur-card {
    flex: 1; background: #1A4A2E; border: 1px solid #2A6040;
    border-radius: 10px; padding: 10px 12px;
  }
  .cur-card .cur-label { font-size: 10px; color: #7AB89A; margin-bottom: 4px; text-transform: uppercase; }
  .cur-card .cur-val   { font-size: 16px; font-weight: 700; color: #F5F7F2; }
  .cur-card .cur-sub   { font-size: 10px; color: #5A9A7A; margin-top: 3px; }

  /* Stat boxes */
  .stat-box {
    background: #FFFFFF; border: 1.5px solid #D4E6DA; border-radius: 16px;
    padding: 20px; text-align: center; height: 100%;
    display: flex; flex-direction: column; justify-content: center;
    box-shadow: 0 1px 6px rgba(11,38,24,0.06);
  }
  .stat-box .stat-label { font-size: 12px; color: #4A7A5A; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .5px; }
  .stat-box .stat-val   { font-size: 30px; font-weight: 800; color: #0B2618; }

  /* Section headers */
  .section-header {
    font-size: 14px; font-weight: 700; color: #0B2618;
    text-transform: uppercase; letter-spacing: .8px;
    border-left: 3px solid #3DFFA0; padding-left: 10px;
    margin: 20px 0 10px 0;
  }

  /* Divider */
  hr { border-color: #D4E6DA !important; margin: 16px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Logo ──────────────────────────────────────────────────────────────────────
def get_logo_b64():
    logo_path = Path(__file__).parent / "mantle_logo.png"
    if logo_path.exists():
        return base64.b64encode(logo_path.read_bytes()).decode()
    return None

logo_b64 = get_logo_b64()

# ── MNT live price ────────────────────────────────────────────────────────────
MNT_FALLBACK = 0.025

@st.cache_data(ttl=300)
def fetch_mnt_price():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "mantle", "vs_currencies": "usd"}, timeout=5,
        )
        r.raise_for_status()
        return float(r.json()["mantle"]["usd"]), "CoinGecko", datetime.now().strftime("%H:%M")
    except Exception:
        pass
    try:
        r = requests.get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "spot", "symbol": "MNTUSDT"}, timeout=5,
        )
        r.raise_for_status()
        return float(r.json()["result"]["list"][0]["lastPrice"]), "Bybit", datetime.now().strftime("%H:%M")
    except Exception:
        pass
    return MNT_FALLBACK, None, None

MNT_PRICE_USD, mnt_source, mnt_fetched_at = fetch_mnt_price()

COUNTRY_CODES = {"KR", "JP", "VN", "CN", "RU", "SEA", "TH", "ID", "PH",
                 "US", "EU", "UK", "AU", "IN", "TR", "AR", "BR", "MX"}
SHEET_ID = "1XFgqvNBBjM4G5x1uIInVLE0ssRYx4YAcGS7AduYBiWg"

# ── Chart colors — readable multi-tone, Mantle green as accent only ──────────
# Spend Over Time bar: muted teal-green
BAR_COLOR    = "#2A9D6E"
# Donut / pie: distinct readable palette
MULTI_COLORS = ["#2A9D6E","#E76F51","#264653","#E9C46A","#457B9D","#A8DADC","#F4A261"]
# Stacked bar: same distinct palette
STACK_COLORS = ["#264653","#2A9D6E","#E9C46A","#E76F51","#457B9D","#A8DADC","#F4A261","#6A4C93"]
# Top KOL bar gradient: slate → teal
KOL_SCALE    = ["#A8DADC","#457B9D","#2A9D6E","#1B4332"]
# Payment status
STATUS_COLORS = {"Paid": "#2A9D6E", "Wait Review": "#E9C46A", "Unpaid / Pending": "#E76F51"}

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    import io as _io
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        df = pd.read_excel(_io.BytesIO(r.content), sheet_name="KOLs Spending")
    except Exception:
        path = Path(__file__).parent / "Q2_2026_Spending_.xlsx"
        df = pd.read_excel(path, sheet_name="KOLs Spending")

    df["Payment Date"] = pd.to_datetime(df["Payment Date"], errors="coerce")
    df["Due Date"]     = pd.to_datetime(df["Due Date"],     errors="coerce")

    def extract_region(desc):
        if pd.isna(desc): return "Global"
        m = re.match(r"\(([^)]+)\s+KOL\)", str(desc))
        if not m: return "Global"
        code = m.group(1).strip().upper()
        return code if code in COUNTRY_CODES else "Global"

    df["Region"] = df["Description"].apply(extract_region)
    df["CurrencyGroup"] = df["Currency"].apply(lambda c: "MNT" if "MNT" in str(c) else "USD")
    df["Amount_Native"] = df["Total Amount"].astype(float)

    def to_usd(row):
        amt, cur = row["Total Amount"], row["Currency"]
        if cur in ("USDC", "USDT", "MNT (USD)"): return float(amt)
        elif cur in ("MNT", "MNT - L2"):          return float(amt) * MNT_PRICE_USD
        return float(amt)

    df["Amount_USD"] = df.apply(to_usd, axis=1)
    df["Month"]    = df["Payment Date"].dt.strftime("%m/%Y")
    df["Month_dt"] = df["Payment Date"].dt.to_period("M").dt.to_timestamp()
    df["Quarter"]  = df["Payment Date"].dt.to_period("Q").astype(str)
    return df

df = load_data()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Filters")
    granularity = st.radio("View by", ["Month", "Quarter"], horizontal=True)

    all_months   = sorted(df["Month"].dropna().unique())
    all_quarters = sorted(df["Quarter"].dropna().unique())

    if granularity == "Month":
        selected_periods = st.multiselect("Months", all_months, default=all_months, placeholder="All months")
    else:
        selected_periods = st.multiselect("Quarters", all_quarters, default=all_quarters, placeholder="All quarters")

    all_regions = sorted(df["Region"].dropna().unique())
    selected_regions = st.multiselect("Region / Market", all_regions, default=all_regions, placeholder="All regions")

    all_statuses = ["Paid", "Wait Review", "Unpaid / Pending"]
    selected_statuses = st.multiselect("Payment Status", all_statuses, default=all_statuses, placeholder="All statuses")

    st.markdown("---")
    dot = "🟢" if mnt_source else "🟡"
    src_txt = f"{mnt_source} · {mnt_fetched_at}" if mnt_source else "Fallback"
    st.markdown(f"{dot} **MNT/USDT** `${MNT_PRICE_USD:.5f}` · {src_txt}")
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

# ── Apply filters ─────────────────────────────────────────────────────────────
mask = pd.Series(True, index=df.index)
if granularity == "Month":
    if selected_periods: mask &= df["Month"].isin(selected_periods)
else:
    if selected_periods: mask &= df["Quarter"].isin(selected_periods)
if selected_regions:  mask &= df["Region"].isin(selected_regions)
if "Paid" not in selected_statuses:             mask &= df["Status"] != "Paid"
if "Wait Review" not in selected_statuses:      mask &= df["Status"] != "Wait Review"
if "Unpaid / Pending" not in selected_statuses: mask &= df["Status"].notna()

fdf = df[mask].copy()

# ── Header row ────────────────────────────────────────────────────────────────
dot = "🟢" if mnt_source else "🟡"
src_txt = f"{mnt_source} · {mnt_fetched_at}" if mnt_source else "Fallback price"

logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:44px;margin-right:12px;vertical-align:middle">' if logo_b64 else ""

col_title, col_mnt, col_info = st.columns([2.5, 1.8, 2.2])

with col_title:
    st.markdown(f"""
    <div style="display:flex;align-items:center;padding-top:4px">
      {logo_html}
      <div>
        <div style="font-size:1.55rem;font-weight:900;color:#0B2618;line-height:1.1">KOLs Spending Dashboard</div>
        <div style="font-size:13px;color:#4A7A5A;font-weight:500">2026 · Mantle Network</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_mnt:
    st.markdown(f"""
    <div style="padding-top:8px">
      <div class="pill">
        <span class="pill-label">MNT / USDT &nbsp;{dot}</span>
        <span class="pill-val">1 MNT = ${MNT_PRICE_USD:.4f} USDT</span>
        <span class="pill-src">{src_txt}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_info:
    st.markdown("""
    <div style="padding-top:8px">
      <div class="info-pill">
        🔄 <b>Auto-updated</b> every 5 min from source data.<br>
        For issues or data updates, contact <b>Minh Anh</b>.
      </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

if fdf.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
usdt_total = fdf[fdf["Currency"] == "USDT"]["Amount_Native"].sum()
usdc_total = fdf[fdf["Currency"] == "USDC"]["Amount_Native"].sum()
mnt_native = fdf[fdf["CurrencyGroup"] == "MNT"]["Amount_Native"].sum()
mnt_in_usd = mnt_native * MNT_PRICE_USD
total_usd  = usdt_total + usdc_total + mnt_in_usd

col_total, col_tx, col_kol, col_reg = st.columns([2, 1, 1, 1])

with col_total:
    st.markdown(f"""
    <div class="total-box">
      <div class="total-label">Total Spend (USD Equivalent)</div>
      <div class="total-val">${total_usd:,.0f}</div>
      <div class="cur-row">
        <div class="cur-card">
          <div class="cur-label">USDT</div>
          <div class="cur-val">${usdt_total:,.0f}</div>
        </div>
        <div class="cur-card">
          <div class="cur-label">USDC</div>
          <div class="cur-val">${usdc_total:,.0f}</div>
        </div>
        <div class="cur-card">
          <div class="cur-label">MNT (all)</div>
          <div class="cur-val">{mnt_native:,.0f}</div>
          <div class="cur-sub">≈ ${mnt_in_usd:,.0f} USD</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_tx:
    st.markdown(f"""
    <div class="stat-box">
      <div class="stat-label">Transactions</div>
      <div class="stat-val">{len(fdf):,}</div>
    </div>
    """, unsafe_allow_html=True)

with col_kol:
    st.markdown(f"""
    <div class="stat-box">
      <div class="stat-label">KOLs</div>
      <div class="stat-val">{fdf['Vendor name'].nunique():,}</div>
    </div>
    """, unsafe_allow_html=True)

with col_reg:
    st.markdown(f"""
    <div class="stat-box">
      <div class="stat-label">Regions</div>
      <div class="stat-val">{fdf['Region'].nunique():,}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

# ── Chart helpers ─────────────────────────────────────────────────────────────
CHART_BG = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
FONT     = dict(family="sans-serif", color="#0B2618")

if granularity == "Month":
    month_order = (
        fdf.groupby(["Month","Month_dt"])["Amount_USD"].sum()
        .reset_index().sort_values("Month_dt")["Month"].tolist()
    )
    month_order = list(dict.fromkeys(month_order))

# ── Row 1: Spend over time | Spend by Region ──────────────────────────────────
st.markdown('<div class="section-header">Spend Overview</div>', unsafe_allow_html=True)
c1, c2 = st.columns([3, 2])

with c1:
    st.markdown("**Spend Over Time**")
    if granularity == "Month":
        trend = fdf.groupby(["Month_dt","Month"])["Amount_USD"].sum().reset_index().sort_values("Month_dt")
        fig_line = px.bar(trend, x="Month", y="Amount_USD", text_auto=".2s",
                          color_discrete_sequence=[BAR_COLOR],
                          labels={"Amount_USD":"USD","Month":""},
                          category_orders={"Month": month_order})
    else:
        trend = fdf.groupby("Quarter")["Amount_USD"].sum().reset_index().sort_values("Quarter")
        fig_line = px.bar(trend, x="Quarter", y="Amount_USD", text_auto=".2s",
                          color_discrete_sequence=[BAR_COLOR],
                          labels={"Amount_USD":"USD","Quarter":""})
    fig_line.update_traces(textposition="outside", textfont_color="#0B2618", marker_line_color="white", marker_line_width=1)
    fig_line.update_layout(**CHART_BG, font=FONT, margin=dict(l=0,r=0,t=10,b=0), height=300,
                           yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                           yaxis=dict(gridcolor="#D4E6DA"), xaxis=dict(gridcolor="#D4E6DA"))
    st.plotly_chart(fig_line, use_container_width=True)

with c2:
    st.markdown("**Spend by Region**")
    region_df = fdf.groupby("Region")["Amount_USD"].sum().reset_index().sort_values("Amount_USD", ascending=False)
    fig_pie = px.pie(region_df, names="Region", values="Amount_USD", hole=0.45,
                     color_discrete_sequence=MULTI_COLORS)
    fig_pie.update_traces(textposition="outside", textinfo="label+percent",
                          textfont=dict(color="#0B2618", size=12),
                          outsidetextfont=dict(color="#0B2618", size=12))
    fig_pie.update_layout(**CHART_BG, font=FONT, showlegend=True,
                          legend=dict(orientation="v", x=1.02, y=0.5,
                                      font=dict(size=11, color="#0B2618")),
                          margin=dict(l=40,r=120,t=30,b=30), height=340)
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Heatmap with row/col totals ───────────────────────────────────────────────
st.markdown('<div class="section-header">Region × Period Breakdown</div>', unsafe_allow_html=True)

if granularity == "Month":
    pivot_data = (fdf.groupby(["Region","Month"])["Amount_USD"].sum()
                  .reset_index()
                  .pivot(index="Region", columns="Month", values="Amount_USD")
                  .fillna(0))
    pivot_data = pivot_data.reindex(columns=month_order)
else:
    pivot_data = (fdf.groupby(["Region","Quarter"])["Amount_USD"].sum()
                  .reset_index()
                  .pivot(index="Region", columns="Quarter", values="Amount_USD")
                  .fillna(0))
    pivot_data = pivot_data.reindex(sorted(pivot_data.columns), axis=1)

# Add Total col and row
pivot_data["Total"] = pivot_data.sum(axis=1)
total_row           = pivot_data.sum(axis=0)
total_row.name      = "Total"
pivot_with_total    = pd.concat([pivot_data, total_row.to_frame().T])

# Split heatmap data: body (no Total) vs Total row/col rendered separately
import plotly.graph_objects as go

body_data  = pivot_data.drop(columns=["Total"])          # no Total col
body_rows  = list(body_data.index)
body_cols  = list(body_data.columns)
total_col  = pivot_data["Total"].values                   # Total per region row
total_row_vals = pivot_with_total.loc["Total"]            # Total per period + grand total

# --- Main heatmap (body only, no Total row/col) ---
fig_heat = go.Figure()
fig_heat.add_trace(go.Heatmap(
    z=body_data.values,
    x=body_cols,
    y=body_rows,
    colorscale=[[0,"#F8FAFC"],[0.2,"#D4EEE2"],[0.5,"#6DBF9E"],[0.8,"#2A9D6E"],[1,"#1B4332"]],
    showscale=False,
    text=[[f"${v:,.0f}" if v >= 1000 else (f"${v:.0f}" if v > 0 else "—") for v in row] for row in body_data.values],
    texttemplate="%{text}",
    textfont=dict(color="#0B2618", size=11),
    hovertemplate="%{y} · %{x}: $%{z:,.0f}<extra></extra>",
    xgap=2, ygap=2,
))

# Total column annotation (right side of body, same rows)
for i, (region, val) in enumerate(zip(body_rows, total_col)):
    fig_heat.add_annotation(
        x=1.01, y=i, xref="paper", yref="y",
        text=f"<b>${val/1000:.1f}k</b>" if val >= 1000 else f"<b>${val:.0f}</b>",
        showarrow=False, font=dict(size=11, color="#C0392B"),
        xanchor="left", align="left",
    )

fig_heat.update_layout(
    **CHART_BG, font=FONT,
    margin=dict(l=0, r=80, t=30, b=60), height=320,
    xaxis=dict(title="", side="bottom", tickfont=dict(size=11)),
    yaxis=dict(title="", tickfont=dict(size=11), autorange="reversed"),
    shapes=[
        # Outer border around Total col annotation area
        dict(type="rect", xref="paper", yref="paper",
             x0=1.005, x1=1.08, y0=0, y1=1,
             line=dict(color="#E76F51", width=1.5), fillcolor="rgba(231,111,81,0.05)"),
    ],
    annotations=[
        dict(x=1.04, y=1.04, xref="paper", yref="paper",
             text="<b>Total</b>", showarrow=False,
             font=dict(size=11, color="#C0392B"), xanchor="center"),
    ] + [
        dict(x=1.01, y=i, xref="paper", yref="y",
             text=f"<b>${v/1000:.1f}k</b>" if v >= 1000 else f"<b>${v:.0f}</b>",
             showarrow=False, font=dict(size=11, color="#C0392B"),
             xanchor="left", align="left")
        for i, v in enumerate(total_col)
    ],
)
# Remove duplicate annotations added above
fig_heat.layout.annotations = fig_heat.layout.annotations[1:]  # keep only the header + values

st.plotly_chart(fig_heat, use_container_width=True)

# --- Total row as a separate styled table below heatmap ---
period_cols = body_cols
total_vals  = [total_row_vals[c] for c in period_cols]
grand_total = total_row_vals["Total"]

total_row_html = "".join([
    f'<td style="text-align:center;padding:6px 12px;background:#FEF0ED;border:1px solid #E76F51;font-weight:700;color:#C0392B;font-size:12px">${v/1000:.1f}k</td>'
    for v in total_vals
])
grand_html = f'<td style="text-align:center;padding:6px 12px;background:#E76F51;border:1px solid #C0392B;font-weight:800;color:#fff;font-size:12px">${grand_total/1000:.1f}k</td>'

period_headers = "".join([
    f'<th style="text-align:center;padding:4px 12px;color:#4A7A5A;font-size:11px;font-weight:600">{c}</th>'
    for c in period_cols
])

st.markdown(f"""
<div style="overflow-x:auto;margin-top:-8px">
  <table style="width:100%;border-collapse:collapse;font-family:sans-serif">
    <thead>
      <tr>
        <th style="text-align:left;padding:4px 12px;color:#4A7A5A;font-size:11px;min-width:80px"></th>
        {period_headers}
        <th style="text-align:center;padding:4px 12px;color:#C0392B;font-size:11px;font-weight:700">Total</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="font-weight:700;color:#C0392B;font-size:12px;padding:6px 12px;background:#FEF0ED;border:1px solid #E76F51">Total</td>
        {total_row_html}
        {grand_html}
      </tr>
    </tbody>
  </table>
</div>
""", unsafe_allow_html=True)

# ── Stacked bar ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Region Contribution by Period</div>', unsafe_allow_html=True)
if granularity == "Month":
    stack_df = fdf.groupby(["Region","Month","Month_dt"])["Amount_USD"].sum().reset_index().sort_values("Month_dt")
    fig_stack = px.bar(stack_df, x="Month", y="Amount_USD", color="Region",
                       barmode="stack", text_auto=".2s",
                       color_discrete_sequence=STACK_COLORS,
                       labels={"Amount_USD":"USD","Month":""},
                       category_orders={"Month": month_order})
else:
    stack_df = fdf.groupby(["Region","Quarter"])["Amount_USD"].sum().reset_index().sort_values("Quarter")
    fig_stack = px.bar(stack_df, x="Quarter", y="Amount_USD", color="Region",
                       barmode="stack", text_auto=".2s",
                       color_discrete_sequence=STACK_COLORS,
                       labels={"Amount_USD":"USD","Quarter":""})
fig_stack.update_layout(**CHART_BG, font=FONT,
                        margin=dict(l=0,r=0,t=10,b=0), height=340,
                        yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                        yaxis=dict(gridcolor="#D4E6DA"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_stack, use_container_width=True)

# ── Top KOLs | Payment Status ────────────────────────────────────────────────
st.markdown('<div class="section-header">KOL Performance & Payment Status</div>', unsafe_allow_html=True)
c5, c6 = st.columns([3, 2])

with c5:
    st.markdown("**Top 15 KOLs by Spend**")
    top_kols = (fdf.groupby("Vendor name")["Amount_USD"].sum()
                .reset_index().sort_values("Amount_USD", ascending=False).head(15))
    fig_kol = px.bar(top_kols.sort_values("Amount_USD"),
                     x="Amount_USD", y="Vendor name", orientation="h", text_auto=".2s",
                     color="Amount_USD",
                     color_continuous_scale=KOL_SCALE,
                     labels={"Amount_USD":"USD","Vendor name":""})
    fig_kol.update_layout(**CHART_BG, font=FONT,
                          margin=dict(l=0,r=0,t=10,b=0), height=420,
                          xaxis_tickprefix="$", xaxis_tickformat=",.0f",
                          xaxis=dict(gridcolor="#D4E6DA"),
                          coloraxis_showscale=False)
    st.plotly_chart(fig_kol, use_container_width=True)

with c6:
    st.markdown("**Payment Status**")
    status_display = fdf["Status"].fillna("Unpaid / Pending")
    status_df = status_display.value_counts().reset_index()
    status_df.columns = ["Status", "Count"]
    color_map = STATUS_COLORS
    fig_status = px.pie(
        status_df, names="Status", values="Count",
        hole=0.52, color="Status", color_discrete_map=color_map,
    )
    fig_status.update_traces(
        textposition="outside",
        textinfo="label+percent+value",
        textfont=dict(color="#0B2618"),
    )
    fig_status.update_layout(**CHART_BG, font=FONT,
                             showlegend=True,
                             legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
                             margin=dict(l=10,r=10,t=10,b=10), height=380)
    st.plotly_chart(fig_status, use_container_width=True)

# ── Raw data table ────────────────────────────────────────────────────────────
with st.expander("📋 Raw Data Table", expanded=False):
    show_cols = [
        "S/N", "Vendor name", "Region", "Description",
        "Currency", "CurrencyGroup", "Total Amount", "Amount_USD",
        "Payment Date", "Status", "Assignee", "Bank/Safe",
    ]
    st.dataframe(fdf[show_cols].sort_values("Payment Date", ascending=False),
                 use_container_width=True, height=400)
    csv = fdf[show_cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download filtered CSV", csv,
                       file_name="kol_spending_filtered.csv", mime="text/csv")
