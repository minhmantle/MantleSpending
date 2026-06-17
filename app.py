import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────────────
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
  .block-container { padding-top: 2rem; }
  h1 { font-size: 1.8rem !important; }
</style>
""", unsafe_allow_html=True)

# ── MNT price (USD equivalent) ────────────────────────────────────────────────
MNT_PRICE_USD = 0.025   # approximate — update as needed

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    path = Path(__file__).parent / "Q2_2026_Spending_.xlsx"
    df = pd.read_excel(path, sheet_name="KOLs Spending")

    # Parse dates
    df["Payment Date"] = pd.to_datetime(df["Payment Date"], errors="coerce")
    df["Due Date"]     = pd.to_datetime(df["Due Date"],     errors="coerce")

    # Extract Region from Description  e.g. "(KR KOL) ..."
    def extract_region(desc):
        if pd.isna(desc):
            return "Unknown"
        m = re.match(r"\(([^)]+)\s+KOL\)", str(desc))
        return m.group(1).strip() if m else "Unknown"

    df["Region"] = df["Description"].apply(extract_region)

    # Convert all amounts to USD
    def to_usd(row):
        amt = row["Total Amount"]
        cur = row["Currency"]
        if cur in ("USDC", "USDT", "MNT (USD)"):
            return float(amt)
        elif cur in ("MNT", "MNT - L2"):
            return float(amt) * MNT_PRICE_USD
        return float(amt)

    df["Amount_USD"] = df.apply(to_usd, axis=1)

    # Time helpers
    df["Month"]    = df["Payment Date"].dt.to_period("M").astype(str)
    df["Month_dt"] = df["Payment Date"].dt.to_period("M").dt.to_timestamp()
    df["Quarter"]  = df["Payment Date"].dt.to_period("Q").astype(str)
    df["Year"]     = df["Payment Date"].dt.year

    return df

df = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Filters")

    # Granularity
    granularity = st.radio("View by", ["Month", "Quarter"], horizontal=True)

    # Time filter
    all_months = sorted(df["Month"].dropna().unique())
    all_quarters = sorted(df["Quarter"].dropna().unique())

    if granularity == "Month":
        selected_periods = st.multiselect(
            "Select Months", all_months, default=all_months,
        )
    else:
        selected_periods = st.multiselect(
            "Select Quarters", all_quarters, default=all_quarters,
        )

    # Region filter
    all_regions = sorted(df["Region"].dropna().unique())
    selected_regions = st.multiselect(
        "Region / Market", all_regions, default=all_regions,
    )

    # Currency filter
    all_currencies = sorted(df["Currency"].dropna().unique())
    selected_currencies = st.multiselect(
        "Original Currency", all_currencies, default=all_currencies,
    )

    # Status filter
    all_statuses = ["Paid", "Wait Review", "Unpaid / Pending"]
    status_map   = {"Paid": "Paid", "Wait Review": "Wait Review"}
    selected_statuses = st.multiselect(
        "Payment Status", all_statuses, default=all_statuses,
    )

    st.markdown("---")
    st.caption(f"MNT price used: **${MNT_PRICE_USD}**")

# ── Apply filters ─────────────────────────────────────────────────────────────
mask = pd.Series(True, index=df.index)

if granularity == "Month":
    mask &= df["Month"].isin(selected_periods)
else:
    mask &= df["Quarter"].isin(selected_periods)

mask &= df["Region"].isin(selected_regions)
mask &= df["Currency"].isin(selected_currencies)

# Status filter: NaN rows = Unpaid/Pending
if "Paid" not in selected_statuses:
    mask &= df["Status"] != "Paid"
if "Wait Review" not in selected_statuses:
    mask &= df["Status"] != "Wait Review"
if "Unpaid / Pending" not in selected_statuses:
    mask &= df["Status"].notna()

fdf = df[mask].copy()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📊 KOL Spending Dashboard")
st.caption("Source: Q2_2026_Spending_.xlsx  ·  All amounts converted to USD")

if fdf.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Spend (USD)", f"${fdf['Amount_USD'].sum():,.0f}")
k2.metric("# Transactions",    f"{len(fdf):,}")
k3.metric("# KOLs",            f"{fdf['Vendor name'].nunique():,}")
k4.metric("# Regions",         f"{fdf['Region'].nunique():,}")

st.markdown("---")

# ── Row 1: Spend over time  |  Spend by Region ────────────────────────────────
c1, c2 = st.columns([3, 2])

with c1:
    st.subheader("💰 Spend Over Time")
    group_col = "Month_dt" if granularity == "Month" else "Quarter"
    label_col = "Month"    if granularity == "Month" else "Quarter"

    if granularity == "Month":
        trend = (
            fdf.groupby("Month_dt")["Amount_USD"]
            .sum()
            .reset_index()
            .sort_values("Month_dt")
        )
        trend["Label"] = trend["Month_dt"].dt.strftime("%b %Y")
        x_col, x_label = "Month_dt", "Label"
    else:
        trend = (
            fdf.groupby("Quarter")["Amount_USD"]
            .sum()
            .reset_index()
            .sort_values("Quarter")
        )
        x_col = "Quarter"

    fig_line = px.bar(
        trend, x=x_col, y="Amount_USD",
        text_auto=".2s",
        color_discrete_sequence=["#5c9fff"],
        labels={"Amount_USD": "USD", x_col: ""},
    )
    fig_line.update_traces(textposition="outside")
    fig_line.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=320,
        yaxis_tickprefix="$", yaxis_tickformat=",.0f",
    )
    if granularity == "Month":
        fig_line.update_xaxes(tickformat="%b %Y")
    st.plotly_chart(fig_line, use_container_width=True)

with c2:
    st.subheader("🌏 Spend by Region")
    region_df = (
        fdf.groupby("Region")["Amount_USD"]
        .sum()
        .reset_index()
        .sort_values("Amount_USD", ascending=False)
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

# ── Row 2: Region × Time heatmap  |  Currency breakdown ──────────────────────
c3, c4 = st.columns([3, 2])

with c3:
    st.subheader("🗺️ Region × Month Heatmap")
    pivot_col = "Month" if granularity == "Month" else "Quarter"
    pivot = (
        fdf.groupby(["Region", pivot_col])["Amount_USD"]
        .sum()
        .reset_index()
        .pivot(index="Region", columns=pivot_col, values="Amount_USD")
        .fillna(0)
    )
    # Sort columns chronologically
    pivot = pivot.reindex(sorted(pivot.columns), axis=1)

    fig_heat = px.imshow(
        pivot,
        text_auto=".2s",
        color_continuous_scale="Blues",
        aspect="auto",
        labels=dict(color="USD"),
    )
    fig_heat.update_layout(
        margin=dict(l=0, r=0, t=10, b=0), height=320,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(tickprefix="$", tickformat=",.0f"),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

with c4:
    st.subheader("💱 Currency Mix")
    cur_df = (
        fdf.groupby("Currency")["Amount_USD"]
        .sum()
        .reset_index()
        .sort_values("Amount_USD", ascending=True)
    )
    fig_bar_cur = px.bar(
        cur_df, x="Amount_USD", y="Currency",
        orientation="h",
        text_auto=".2s",
        color_discrete_sequence=["#a78bfa"],
        labels={"Amount_USD": "USD", "Currency": ""},
    )
    fig_bar_cur.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=320,
        xaxis_tickprefix="$", xaxis_tickformat=",.0f",
    )
    st.plotly_chart(fig_bar_cur, use_container_width=True)

# ── Row 3: Stacked bar Region × Time ─────────────────────────────────────────
st.subheader("📈 Region Spend — Stacked by Period")
pivot_col = "Month" if granularity == "Month" else "Quarter"

stack_df = (
    fdf.groupby(["Region", pivot_col])["Amount_USD"]
    .sum()
    .reset_index()
    .sort_values(pivot_col)
)

fig_stack = px.bar(
    stack_df, x=pivot_col, y="Amount_USD", color="Region",
    barmode="stack",
    text_auto=".2s",
    color_discrete_sequence=px.colors.qualitative.Safe,
    labels={"Amount_USD": "USD", pivot_col: ""},
)
fig_stack.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0), height=360,
    yaxis_tickprefix="$", yaxis_tickformat=",.0f",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_stack, use_container_width=True)

# ── Row 4: Top KOLs  |  Status breakdown ─────────────────────────────────────
c5, c6 = st.columns([3, 2])

with c5:
    st.subheader("🏆 Top 15 KOLs by Spend")
    top_kols = (
        fdf.groupby("Vendor name")["Amount_USD"]
        .sum()
        .reset_index()
        .sort_values("Amount_USD", ascending=False)
        .head(15)
    )
    fig_kol = px.bar(
        top_kols.sort_values("Amount_USD"),
        x="Amount_USD", y="Vendor name",
        orientation="h",
        text_auto=".2s",
        color="Amount_USD",
        color_continuous_scale="Teal",
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
    status_df = (
        status_display.value_counts().reset_index()
    )
    status_df.columns = ["Status", "Count"]

    color_map = {"Paid": "#22c55e", "Wait Review": "#f59e0b", "Unpaid / Pending": "#ef4444"}
    fig_status = px.pie(
        status_df, names="Status", values="Count",
        hole=0.5,
        color="Status",
        color_discrete_map=color_map,
    )
    fig_status.update_traces(textposition="outside", textinfo="label+value")
    fig_status.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=260,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_status, use_container_width=True)

    # Amount by status
    status_amt = (
        fdf.groupby(fdf["Status"].fillna("Unpaid / Pending"))["Amount_USD"]
        .sum()
        .reset_index()
    )
    status_amt.columns = ["Status", "USD"]
    fig_status_amt = px.bar(
        status_amt, x="Status", y="USD",
        text_auto=".2s",
        color="Status",
        color_discrete_map=color_map,
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
        "Currency", "Total Amount", "Amount_USD",
        "Payment Date", "Status", "Assignee", "Bank/Safe",
    ]
    st.dataframe(
        fdf[show_cols].sort_values("Payment Date", ascending=False),
        use_container_width=True,
        height=400,
    )

    csv = fdf[show_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download filtered CSV", csv,
        file_name="kol_spending_filtered.csv",
        mime="text/csv",
    )
