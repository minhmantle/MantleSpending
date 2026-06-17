import streamlit as st
import pandas as pd
import plotly.express as px
import re
import requests
from datetime import datetime
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KOL Spending Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stMetric"] { background: #1e1e2e; border-radius: 12px; padding: 16px; }
  [data-testid="stMetricLabel"] { font-size: 13px; color: #a0a0b0; }
  [data-testid="stMetricValue"] { font-size: 26px; font-weight: 700; }
  [data-testid="stMetricDelta"] { font-size: 13px !important; }
  .block-container { padding-top: 1.2rem; }
  h1 { font-size: 1.8rem !important; }

  /* MNT pill — small, top-right */
  .mnt-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #1e1e2e;
    border: 1px solid #3a3a5a;
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 13px;
    color: #c4b5fd;
    float: right;
    margin-top: 4px;
  }
  .mnt-pill b { color: #a78bfa; font-size: 14px; }
  .mnt-dot { font-size: 10px; }

  /* Sub-metric cards */
  .sub-card {
    background: #16162a;
    border: 1px solid #2e2e4a;
    border-radius: 10px;
    padding: 10px 16px;
    margin-top: 8px;
  }
  .sub-card-label { font-size: 12px; color: #6b7280; margin-bottom: 2px; }
  .sub-card-value { font-size: 18px; font-weight: 700; color: #e2e8f0; }
  .sub-card-sub   { font-size: 12px; color: #a0a0b0; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ── MNT live price ────────────────────────────────────────────────────────────
MNT_FALLBACK = 0.025

@st.cache_data(ttl=300)
def fetch_mnt_price():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "mantle", "vs_currencies": "usd"},
            timeout=5,
        )
        r.raise_for_status()
        return float(r.json()["mantle"]["usd"]), "CoinGecko", datetime.now().strftime("%H:%M")
    except Exception:
        pass
    try:
        r = requests.get(
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "spot", "symbol": "MNTUSDT"},
            timeout=5,
        )
        r.raise_for_status()
        return float(r.json()["result"]["list"][0]["lastPrice"]), "Bybit", datetime.now().strftime("%H:%M")
    except Exception:
        pass
    return MNT_FALLBACK, None, None

MNT_PRICE_USD, mnt_source, mnt_fetched_at = fetch_mnt_price()

# ── Constants ─────────────────────────────────────────────────────────────────
COUNTRY_CODES = {"KR", "JP", "VN", "CN", "RU", "SEA", "TH", "ID", "PH",
                 "US", "EU", "UK", "AU", "IN", "TR", "AR", "BR", "MX"}

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    path = Path(__file__).parent / "Q2_2026_Spending_.xlsx"
    df = pd.read_excel(path, sheet_name="KOLs Spending")

    df["Payment Date"] = pd.to_datetime(df["Payment Date"], errors="coerce")
    df["Due Date"]     = pd.to_datetime(df["Due Date"],     errors="coerce")

    def extract_region(desc):
        if pd.isna(desc):
            return "Global"
        m = re.match(r"\(([^)]+)\s+KOL\)", str(desc))
        if not m:
            return "Global"
        code = m.group(1).strip().upper()
        return code if code in COUNTRY_CODES else "Global"

    df["Region"] = df["Description"].apply(extract_region)

    df["CurrencyGroup"] = df["Currency"].apply(
        lambda c: "MNT" if "MNT" in str(c) else "USD"
    )
    df["Amount_Native"] = df["Total Amount"].astype(float)

    def to_usd(row):
        amt, cur = row["Total Amount"], row["Currency"]
        if cur in ("USDC", "USDT", "MNT (USD)"):
            return float(amt)
        elif cur in ("MNT", "MNT - L2"):
            return float(amt) * MNT_PRICE_USD
        return float(amt)

    df["Amount_USD"] = df.apply(to_usd, axis=1)

    df["Month"]    = df["Payment Date"].dt.strftime("%m/%Y")
    df["Month_dt"] = df["Payment Date"].dt.to_period("M").dt.to_timestamp()
    df["Quarter"]  = df["Payment Date"].dt.to_period("Q").astype(str)

    return df

df = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Filters")

    granularity = st.radio("View by", ["Month", "Quarter"], horizontal=True)

    all_months   = sorted(df["Month"].dropna().unique())
    all_quarters = sorted(df["Quarter"].dropna().unique())

    if granularity == "Month":
        selected_periods = st.multiselect(
            "Months", all_months, default=all_months,
            placeholder="All months",
        )
    else:
        selected_periods = st.multiselect(
            "Quarters", all_quarters, default=all_quarters,
            placeholder="All quarters",
        )

    all_regions = sorted(df["Region"].dropna().unique())
    selected_regions = st.multiselect(
        "Region / Market", all_regions, default=all_regions,
        placeholder="All regions",
    )

    all_statuses = ["Paid", "Wait Review", "Unpaid / Pending"]
    selected_statuses = st.multiselect(
        "Payment Status", all_statuses, default=all_statuses,
        placeholder="All statuses",
    )

    st.markdown("---")
    if mnt_source:
        st.success(f"**MNT/USDT** `${MNT_PRICE_USD:.5f}`  \n🟢 {mnt_source} · {mnt_fetched_at}")
    else:
        st.warning(f"**MNT/USDT** `${MNT_PRICE_USD:.5f}`  \n🟡 Fallback")
    if st.button("🔄 Refresh price"):
        st.cache_data.clear()
        st.rerun()

# ── Apply filters ─────────────────────────────────────────────────────────────
mask = pd.Series(True, index=df.index)
if granularity == "Month":
    if selected_periods:
        mask &= df["Month"].isin(selected_periods)
else:
    if selected_periods:
        mask &= df["Quarter"].isin(selected_periods)
if selected_regions:
    mask &= df["Region"].isin(selected_regions)
if "Paid" not in selected_statuses:
    mask &= df["Status"] != "Paid"
if "Wait Review" not in selected_statuses:
    mask &= df["Status"] != "Wait Review"
if "Unpaid / Pending" not in selected_statuses:
    mask &= df["Status"].notna()

fdf = df[mask].copy()

# ── Header row: title + MNT pill ──────────────────────────────────────────────
dot = "🟢" if mnt_source else "🟡"
src = mnt_source or "fallback"
h1, h2 = st.columns([4, 1])
with h1:
    st.title("📊 KOL Spending Dashboard")
with h2:
    st.markdown(f"""
    <div class="mnt-pill">
      <span class="mnt-dot">{dot}</span>
      <span>1 MNT = <b>${MNT_PRICE_USD:.4f}</b> USDT</span>
      <span style="color:#4b5563;font-size:11px">{src}</span>
    </div>
    """, unsafe_allow_html=True)

if fdf.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── KPI: total + breakdown ────────────────────────────────────────────────────
usd_total   = fdf[fdf["CurrencyGroup"] == "USD"]["Amount_Native"].sum()
mnt_native  = fdf[fdf["CurrencyGroup"] == "MNT"]["Amount_Native"].sum()
mnt_in_usd  = mnt_native * MNT_PRICE_USD
total_usd   = usd_total + mnt_in_usd

usdc_total = fdf[fdf["Currency"] == "USDC"]["Amount_Native"].sum()
usdt_total = fdf[fdf["Currency"] == "USDT"]["Amount_Native"].sum()

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric("💵 Total Spend (USD equiv.)", f"${total_usd:,.0f}")
    st.markdown(f"""
    <div class="sub-card">
      <div class="sub-card-label">USDT</div>
      <div class="sub-card-value">${usdt_total:,.0f}</div>
    </div>
    <div class="sub-card">
      <div class="sub-card-label">USDC</div>
      <div class="sub-card-value">${usdc_total:,.0f}</div>
    </div>
    <div class="sub-card">
      <div class="sub-card-label">MNT (all variants)</div>
      <div class="sub-card-value">{mnt_native:,.0f} MNT</div>
      <div class="sub-card-sub">≈ ${mnt_in_usd:,.0f} USD @ ${MNT_PRICE_USD:.4f}</div>
    </div>
    """, unsafe_allow_html=True)

k2.metric("🔁 # Transactions", f"{len(fdf):,}")
k3.metric("👤 # KOLs", f"{fdf['Vendor name'].nunique():,}")
k4.metric("🌏 # Regions", f"{fdf['Region'].nunique():,}")

st.markdown("---")

# ── Row 1: Spend over time  |  Spend by Region ───────────────────────────────
c1, c2 = st.columns([3, 2])

with c1:
    st.subheader("💰 Spend Over Time")
    if granularity == "Month":
        trend = (
            fdf.groupby(["Month_dt", "Month"])["Amount_USD"].sum()
            .reset_index().sort_values("Month_dt")
        )
        fig_line = px.bar(
            trend, x="Month", y="Amount_USD",
            text_auto=".2s",
            color_discrete_sequence=["#5c9fff"],
            labels={"Amount_USD": "USD", "Month": ""},
            category_orders={"Month": trend["Month"].tolist()},
        )
    else:
        trend = (
            fdf.groupby("Quarter")["Amount_USD"].sum()
            .reset_index().sort_values("Quarter")
        )
        fig_line = px.bar(
            trend, x="Quarter", y="Amount_USD",
            text_auto=".2s",
            color_discrete_sequence=["#5c9fff"],
            labels={"Amount_USD": "USD", "Quarter": ""},
        )
    fig_line.update_traces(textposition="outside")
    fig_line.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=320,
        yaxis_tickprefix="$", yaxis_tickformat=",.0f",
    )
    st.plotly_chart(fig_line, use_container_width=True)

with c2:
    st.subheader("🌏 Spend by Region")
    region_df = (
        fdf.groupby("Region")["Amount_USD"].sum()
        .reset_index().sort_values("Amount_USD", ascending=False)
    )
    fig_pie = px.pie(
        region_df, names="Region", values="Amount_USD",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig_pie.update_traces(textposition="outside", textinfo="label+percent")
    fig_pie.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=320,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Row 2: Heatmap full width ─────────────────────────────────────────────────
st.subheader("🗺️ Region × Period Heatmap (USD)")
pivot_col = "Month" if granularity == "Month" else "Quarter"

if granularity == "Month":
    # Sort months chronologically using Month_dt
    month_order = (
        fdf.groupby(["Month", "Month_dt"])["Amount_USD"].sum()
        .reset_index().sort_values("Month_dt")["Month"].tolist()
    )
    month_order = list(dict.fromkeys(month_order))  # dedupe preserve order
    pivot_data = (
        fdf.groupby(["Region", "Month"])["Amount_USD"].sum()
        .reset_index()
        .pivot(index="Region", columns="Month", values="Amount_USD")
        .fillna(0)
    )
    pivot_data = pivot_data.reindex(columns=month_order)
else:
    pivot_data = (
        fdf.groupby(["Region", "Quarter"])["Amount_USD"].sum()
        .reset_index()
        .pivot(index="Region", columns="Quarter", values="Amount_USD")
        .fillna(0)
    )
    pivot_data = pivot_data.reindex(sorted(pivot_data.columns), axis=1)

fig_heat = px.imshow(
    pivot_data, text_auto=".2s",
    color_continuous_scale="Blues", aspect="auto",
    labels=dict(color="USD"),
)
fig_heat.update_layout(
    margin=dict(l=0, r=0, t=10, b=0), height=300,
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    coloraxis_colorbar=dict(tickprefix="$", tickformat=",.0f"),
    xaxis_title="", yaxis_title="",
)
st.plotly_chart(fig_heat, use_container_width=True)

# ── Row 3: Stacked bar ────────────────────────────────────────────────────────
st.subheader("📈 Region Spend — Stacked by Period")
if granularity == "Month":
    stack_df = (
        fdf.groupby(["Region", "Month", "Month_dt"])["Amount_USD"].sum()
        .reset_index().sort_values("Month_dt")
    )
    x_col = "Month"
    cat_orders = {"Month": month_order}
else:
    stack_df = (
        fdf.groupby(["Region", "Quarter"])["Amount_USD"].sum()
        .reset_index().sort_values("Quarter")
    )
    x_col = "Quarter"
    cat_orders = {}

fig_stack = px.bar(
    stack_df, x=x_col, y="Amount_USD", color="Region",
    barmode="stack", text_auto=".2s",
    color_discrete_sequence=px.colors.qualitative.Safe,
    labels={"Amount_USD": "USD", x_col: ""},
    category_orders=cat_orders,
)
fig_stack.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0), height=360,
    yaxis_tickprefix="$", yaxis_tickformat=",.0f",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_stack, use_container_width=True)

# ── Row 4: Top KOLs  |  Status ───────────────────────────────────────────────
c5, c6 = st.columns([3, 2])

with c5:
    st.subheader("🏆 Top 15 KOLs by Spend")
    top_kols = (
        fdf.groupby("Vendor name")["Amount_USD"].sum()
        .reset_index().sort_values("Amount_USD", ascending=False).head(15)
    )
    fig_kol = px.bar(
        top_kols.sort_values("Amount_USD"),
        x="Amount_USD", y="Vendor name",
        orientation="h", text_auto=".2s",
        color="Amount_USD", color_continuous_scale="Teal",
        labels={"Amount_USD": "USD", "Vendor name": ""},
    )
    fig_kol.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=420,
        xaxis_tickprefix="$", xaxis_tickformat=",.0f",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_kol, use_container_width=True)

with c6:
    st.subheader("✅ Payment Status")
    status_display = fdf["Status"].fillna("Unpaid / Pending")
    status_df = status_display.value_counts().reset_index()
    status_df.columns = ["Status", "Count"]
    color_map = {"Paid": "#22c55e", "Wait Review": "#f59e0b", "Unpaid / Pending": "#ef4444"}
    fig_status = px.pie(
        status_df, names="Status", values="Count",
        hole=0.5, color="Status", color_discrete_map=color_map,
    )
    fig_status.update_traces(textposition="outside", textinfo="label+value")
    fig_status.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=260,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_status, use_container_width=True)

    status_amt = (
        fdf.groupby(fdf["Status"].fillna("Unpaid / Pending"))["Amount_USD"].sum().reset_index()
    )
    status_amt.columns = ["Status", "USD"]
    fig_status_amt = px.bar(
        status_amt, x="Status", y="USD",
        text_auto=".2s", color="Status", color_discrete_map=color_map,
        labels={"USD": "USD", "Status": ""},
    )
    fig_status_amt.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=220,
        yaxis_tickprefix="$", yaxis_tickformat=",.0f",
        showlegend=False,
    )
    st.plotly_chart(fig_status_amt, use_container_width=True)

# ── Raw data table ────────────────────────────────────────────────────────────
with st.expander("📋 Raw Data Table", expanded=False):
    show_cols = [
        "S/N", "Vendor name", "Region", "Description",
        "Currency", "CurrencyGroup", "Total Amount", "Amount_USD",
        "Payment Date", "Status", "Assignee", "Bank/Safe",
    ]
    st.dataframe(
        fdf[show_cols].sort_values("Payment Date", ascending=False),
        use_container_width=True, height=400,
    )
    csv = fdf[show_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download filtered CSV", csv,
        file_name="kol_spending_filtered.csv", mime="text/csv",
    )
