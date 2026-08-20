"""EarningsLens Streamlit Dashboard — Phase 4.

Run with: streamlit run src/dashboard/app.py
"""

import sys
import os
import json

# Ensure project root is on sys.path for imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import DB_PATH, SCORE_DIMENSIONS
from src.storage.db import init_db
from src.trends.metrics import (
    load_scores_from_db,
    compute_qoq_score_change,
    compute_rolling_3q_average,
    compute_trend_label,
    find_biggest_single_quarter_drop,
)

# ---------- Page config ----------
st.set_page_config(
    page_title="EarningsLens",
    page_icon="📊",
    layout="wide",
)

# ---------- Load data ----------
conn = init_db(str(DB_PATH))
scores_df = load_scores_from_db(conn)
conn.close()

if scores_df.empty:
    st.warning("No scores found in database. Run scoring first (Phase 2).")
    st.stop()

# ---------- Sidebar: company selector ----------
st.sidebar.title("EarningsLens")
st.sidebar.markdown("Management credibility scoring for Indian earnings calls.")

companies = sorted(scores_df["company"].unique())
selected_company = st.sidebar.selectbox("Company", companies)

company_df = scores_df[scores_df["company"] == selected_company].copy()
company_df = company_df.sort_values(["year", "quarter"]).reset_index(drop=True)

st.title(f"📊 {selected_company}")

# ---------- Tabs ----------
tab_scores, tab_trends, tab_drops, tab_raw = st.tabs(
    ["Scores", "Trends", "Alerts", "Raw Data"]
)

# ---- Tab 1: Scores ----
with tab_scores:
    st.subheader("Quarterly Scores")

    # Build a display dataframe with readable column names
    display_cols = ["quarter", "year"] + [d for d in SCORE_DIMENSIONS if d in company_df.columns]
    display_df = company_df[display_cols].copy()
    display_df["period"] = display_df["year"].astype(str) + " " + display_df["quarter"]
    display_df = display_df.drop(columns=["quarter", "year"])

    # Line chart for each dimension
    dims_available = [d for d in SCORE_DIMENSIONS if d in company_df.columns]
    if dims_available:
        fig = go.Figure()
        for dim in dims_available:
            fig.add_trace(go.Scatter(
                x=display_df["period"],
                y=company_df[dim],
                name=dim.replace("_", " ").title(),
                mode="lines+markers",
                marker=dict(size=8),
            ))
        fig.update_layout(
            yaxis_title="Score (1-10)",
            xaxis_title="Quarter",
            yaxis=dict(range=[0, 10.5]),
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        )
        st.plotly_chart(fig, width="stretch")

    # Trend labels
    trends = compute_trend_label(company_df)
    trend_cols = [f"{d}_trend" for d in SCORE_DIMENSIONS if f"{d}_trend" in trends.columns]
    if trend_cols:
        st.subheader("Latest Trend Labels")
        latest = trends.iloc[-1]
        cols = st.columns(len(trend_cols))
        for i, tc in enumerate(trend_cols):
            dim_name = tc.replace("_trend", "").replace("_", " ").title()
            label = latest[tc]
            color = {"IMPROVING": "green", "STABLE": "gray", "DETERIORATING": "red"}.get(label, "gray")
            cols[i].markdown(f"**{dim_name}**  \n:{color}[{label}]")

# ---- Tab 2: Trends ----
with tab_trends:
    st.subheader("Quarter-over-Quarter Changes")

    qoq = compute_qoq_score_change(company_df)
    delta_cols = [f"{d}_delta" for d in SCORE_DIMENSIONS if f"{d}_delta" in qoq.columns]
    if delta_cols:
        fig_delta = go.Figure()
        for dc in delta_cols:
            dim_name = dc.replace("_delta", "").replace("_", " ").title()
            fig_delta.add_trace(go.Bar(
                x=qoq.apply(lambda r: f"{r['year']} {r['quarter']}", axis=1),
                y=qoq[dc],
                name=dim_name,
            ))
        fig_delta.update_layout(
            barmode="group",
            yaxis_title="Score Change",
            xaxis_title="Quarter",
            height=400,
        )
        st.plotly_chart(fig_delta, width="stretch")

    st.subheader("Rolling 3-Quarter Averages")
    ma3 = compute_rolling_3q_average(company_df)
    ma3_cols = [f"{d}_ma3" for d in SCORE_DIMENSIONS if f"{d}_ma3" in ma3.columns]
    if ma3_cols:
        fig_ma = go.Figure()
        for mc in ma3_cols:
            dim_name = mc.replace("_ma3", "").replace("_", " ").title()
            fig_ma.add_trace(go.Scatter(
                x=ma3.apply(lambda r: f"{r['year']} {r['quarter']}", axis=1),
                y=ma3[mc],
                name=dim_name,
                mode="lines+markers",
            ))
        fig_ma.update_layout(
            yaxis_title="Rolling Average",
            xaxis_title="Quarter",
            yaxis=dict(range=[0, 10.5]),
            height=400,
        )
        st.plotly_chart(fig_ma, width="stretch")

# ---- Tab 3: Alerts ----
with tab_drops:
    st.subheader("Biggest Single-Quarter Score Increases (Worsening)")
    drops = find_biggest_single_quarter_drop(scores_df)
    company_drops = drops[drops["company"] == selected_company] if not drops.empty else pd.DataFrame()

    if company_drops.empty:
        st.info("No significant worsening detected for this company.")
    else:
        for _, row in company_drops.iterrows():
            dim_name = row["dimension"].replace("_", " ").title()
            prev_q = f"{row.get('prev_year', '?')} {row.get('prev_quarter', '?')}"
            curr_q = f"{row['year']} {row['quarter']}"
            delta = row["delta"]
            st.warning(
                f"**{dim_name}**: {row.get('prev_score', '?')} → {row['score']} "
                f"(+{delta:.0f}) from {prev_q} to {curr_q}"
            )

    # Company-wide deterioration summary
    st.subheader("All Companies — Recent Trend Summary")
    all_trends = compute_trend_label(scores_df)
    if not all_trends.empty:
        latest_all = all_trends.sort_values(["company", "year", "quarter"]).groupby("company").last().reset_index()
        trend_summary = latest_all[["company"] + [f"{d}_trend" for d in SCORE_DIMENSIONS if f"{d}_trend" in latest_all.columns]]
        st.dataframe(trend_summary, width="stretch")

# ---- Tab 4: Raw Data ----
with tab_raw:
    st.subheader("Score Details")
    st.dataframe(company_df, width="stretch")

    st.subheader("Supporting Quotes")
    conn2 = init_db(str(DB_PATH))
    cur = conn2.cursor()
    cur.execute("""
        SELECT t.company, t.quarter, t.year, s.dimension, s.score, s.supporting_quotes
        FROM scores s
        JOIN transcripts t ON s.transcript_id = t.id
        WHERE t.company = ?
        ORDER BY t.year, t.quarter, s.dimension
    """, (selected_company,))
    rows = cur.fetchall()
    conn2.close()

    for r in rows:
        company, quarter, year, dimension, score, quotes_json = r
        quotes = json.loads(quotes_json) if quotes_json else []
        if quotes:
            with st.expander(f"{year} {quarter} — {dimension} (Score: {score})"):
                for q in quotes:
                    st.markdown(f"> {q}")

# ---------- Footer ----------
st.sidebar.markdown("---")
st.sidebar.caption("EarningsLens v0.1 — Phase 4 Dashboard")
