import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import warnings

warnings.filterwarnings("ignore")

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Detailed Inventory Analysis",
    layout="wide"
)

st.markdown("""
<h1 style='color:#31859C; font-size:38px; font-weight:700;'>
Detailed Inventory Analysis Dashboard
</h1>
""", unsafe_allow_html=True)

# =========================================================
# LOAD DATA
# =========================================================

@st.cache_data
def load_data():

    params = pd.read_csv("test_2.csv")
    cons = pd.read_excel("Consumption.xlsx")

    params.columns = params.columns.str.strip()
    cons.columns = cons.columns.str.strip()

    month_map = {
        'janv': 'Jan',
        'févr': 'Feb',
        'mars': 'Mar',
        'avr': 'Apr',
        'mai': 'May',
        'juin': 'Jun',
        'juil': 'Jul',
        'août': 'Aug',
        'sept': 'Sep',
        'oct': 'Oct',
        'nov': 'Nov',
        'déc': 'Dec'
    }

    def parse_french_month(x):

        x = str(x).lower()

        for fr, en in month_map.items():
            x = x.replace(fr, en)

        return pd.to_datetime(x, format='%b-%y')

    cons['Date'] = cons['Month'].apply(parse_french_month)

    cons.rename(columns={
        'Valeur': 'Consumption'
    }, inplace=True)

    return params, cons

params, cons = load_data()

# =========================================================
# REQUIRED COLUMNS
# =========================================================

COL_ROP = 'Reorder Point (ROP) (m2: Monthly)'
COL_EOQ = 'EOQ (Economic Order Quantity)'
COL_LT = 'Lead Time (Days)'

# =========================================================
# PIVOT TABLE
# =========================================================

pivot = cons.pivot_table(
    index='Article',
    columns='Date',
    values='Consumption',
    aggfunc='sum',
    fill_value=0
)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("🔎 Article Selection")

article_list = params['Article'].astype(str).tolist()

selected_article = st.sidebar.selectbox(
    "Select Article",
    article_list
)

# =========================================================
# ARTICLE ROW
# =========================================================

row = params[
    params['Article'].astype(str) == selected_article
]

if row.empty:
    st.error("Article not found")
    st.stop()

row = row.iloc[0]

# =========================================================
# ARTICLE INFO
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Article Information
</h3>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

c1.metric("Article", selected_article)
c2.metric("ABC", row.get("ABC", ""))
c3.metric("HML", row.get("HML", ""))
c4.metric("XYZ", row.get("XYZ classification", ""))

st.info(str(row.get("Désignation article", "")))

# =========================================================
# PARAMETERS
# =========================================================

rop = float(row[COL_ROP]) if pd.notna(row[COL_ROP]) else 0

eoq = float(row[COL_EOQ]) if pd.notna(row[COL_EOQ]) else 0

lt_days = float(row[COL_LT]) if pd.notna(row[COL_LT]) else 30

lt_months = max(1, math.ceil(lt_days / 30))

unit_cost = float(row.get("Unit Cost", 0))

service_level_target = float(
    row.get("Service Level", 0.95)
)

p1, p2, p3, p4 = st.columns(4)

p1.metric("ROP", round(rop, 2))
p2.metric("EOQ", round(eoq, 2))
p3.metric("Lead Time Days", lt_days)
p4.metric("Unit Cost", round(unit_cost, 2))

# =========================================================
# DEMAND DATA
# =========================================================

try:
    article_key = int(selected_article)
except:
    article_key = selected_article

if article_key not in pivot.index:

    st.warning("No consumption data found.")
    st.stop()

art_series = pivot.loc[article_key]

demand_df = pd.DataFrame({
    "Date": art_series.index,
    "Demand": np.abs(art_series.values)
})

# =========================================================
# INVENTORY SIMULATION
# =========================================================

stock = rop + (eoq / 2) if eoq > 0 else rop * 2

on_order = {}

last_order_month = -999

stock_before_list = []
stock_after_list = []
received_list = []
order_qty_list = []
stockout_list = []
avg_stock_list = []

unfilled_demand = 0

for i, demand in enumerate(demand_df["Demand"]):

    # RECEIVE ORDERS

    received = on_order.pop(i, 0)

    stock += received

    stock_before = stock

    # APPLY DEMAND

    stock_raw = stock - demand

    in_stockout = stock_raw < 0

    if in_stockout:

        unfilled_demand += abs(stock_raw)

        stock = 0

    else:

        stock = stock_raw

    # ORDER LOGIC

    months_since_last = i - last_order_month

    can_order = (
        True if in_stockout
        else (months_since_last >= lt_months)
    )

    order_qty = 0

    if stock <= rop and eoq > 0 and can_order:

        arrival = i + lt_months

        if arrival < len(demand_df):

            on_order[arrival] = (
                on_order.get(arrival, 0) + eoq
            )

        last_order_month = i

        order_qty = eoq

    # STORE

    stock_before_list.append(stock_before)
    stock_after_list.append(stock)
    received_list.append(received)
    order_qty_list.append(order_qty)
    stockout_list.append(in_stockout)
    avg_stock_list.append((stock_before + stock) / 2)

# =========================================================
# RESULTS DATAFRAME
# =========================================================

demand_df["Stock_Before"] = stock_before_list
demand_df["Stock_After"] = stock_after_list
demand_df["Received"] = received_list
demand_df["Order_Qty"] = order_qty_list
demand_df["Stockout"] = stockout_list
demand_df["Average_Stock"] = avg_stock_list

# =========================================================
# KPIs
# =========================================================

total_stockouts = sum(stockout_list)

total_demand = demand_df["Demand"].sum()

fill_rate = (
    (1 - unfilled_demand / max(total_demand, 1))
    * 100
)

total_orders = sum(
    demand_df["Order_Qty"] > 0
)

stockout_rate = (
    total_stockouts / len(demand_df)
) * 100

avg_inventory = demand_df[
    "Average_Stock"
].mean()

inventory_turnover = (
    total_demand / max(avg_inventory, 1)
)

avg_monthly_demand = demand_df[
    "Demand"
].mean()

std_monthly_demand = demand_df[
    "Demand"
].std()

cv = (
    std_monthly_demand /
    max(avg_monthly_demand, 1)
)

# =========================================================
# CRITICALITY SCORE
# =========================================================

score = 0

abc = str(row.get("ABC", "C"))
xyz = str(row.get("XYZ classification", "X"))
hml = str(row.get("HML", "L"))

# ABC

if abc == "A":
    score += 3
elif abc == "B":
    score += 2
else:
    score += 1

# XYZ

if xyz == "Z":
    score += 3
elif xyz == "Y":
    score += 2
else:
    score += 1

# HML

if hml == "H":
    score += 2
elif hml == "M":
    score += 1

# STOCKOUT RATE

if stockout_rate > 20:
    score += 4
elif stockout_rate > 10:
    score += 2

# FILL RATE

if fill_rate < 85:
    score += 4
elif fill_rate < 95:
    score += 2

# LEAD TIME

if lt_days > 90:
    score += 2
elif lt_days > 30:
    score += 1

# FINAL CRITICALITY

if score >= 12:
    criticality = "High"

elif score >= 7:
    criticality = "Medium"

else:
    criticality = "Low"

# =========================================================
# MAIN KPIs
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Simulation KPIs
</h3>
""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "Stockout Months",
    total_stockouts
)

k2.metric(
    "Stockout Rate %",
    round(stockout_rate, 2)
)

k3.metric(
    "Fill Rate %",
    round(fill_rate, 2)
)

k4.metric(
    "Criticality",
    criticality
)

k5, k6, k7, k8 = st.columns(4)

k5.metric(
    "Orders Placed",
    total_orders
)

k6.metric(
    "Avg Inventory",
    round(avg_inventory, 2)
)

k7.metric(
    "Inventory Turnover",
    round(inventory_turnover, 2)
)

k8.metric(
    "Demand CV",
    round(cv, 2)
)

# =========================================================
# INVENTORY HEALTH DIAGNOSIS
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Inventory Health Diagnosis
</h3>
""", unsafe_allow_html=True)

diagnosis = []

if stockout_rate > 20 and fill_rate < 85:
    diagnosis.append(
        "Severe understocking risk detected."
    )

if avg_inventory > avg_monthly_demand * 6:
    diagnosis.append(
        "Potential overstock situation."
    )

if cv > 1.2:
    diagnosis.append(
        "Demand variability is very high."
    )

if lt_days > 90:
    diagnosis.append(
        "Long lead time increases supply risk."
    )

if total_orders > 12:
    diagnosis.append(
        "Too many replenishment orders detected."
    )

if not diagnosis:
    diagnosis.append(
        "Inventory policy appears stable."
    )

for d in diagnosis:

    st.warning(d)

# =========================================================
# RECOMMENDATIONS
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Optimization Recommendations
</h3>
""", unsafe_allow_html=True)

recommendations = []

if stockout_rate > 20:

    recommendations.append(
        "Increase reorder point to reduce stockouts."
    )

if fill_rate < 90:

    recommendations.append(
        "Increase safety stock to improve service level."
    )

if total_orders > 12:

    recommendations.append(
        "EOQ may be too small and causing excessive replenishment."
    )

if xyz == "Z":

    recommendations.append(
        "Demand variability is high. Forecast review recommended."
    )

if lt_days > 90:

    recommendations.append(
        "Additional buffer stock recommended due to long lead time."
    )

if avg_inventory > avg_monthly_demand * 6:

    recommendations.append(
        "Reduce EOQ to lower holding costs."
    )

if inventory_turnover < 2:

    recommendations.append(
        "Low inventory turnover detected."
    )

if not recommendations:

    recommendations.append(
        "Current inventory policy is acceptable."
    )

for rec in recommendations:

    st.info(rec)

# =========================================================
# OPTIMIZATION SUGGESTIONS
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Suggested Inventory Parameters
</h3>
""", unsafe_allow_html=True)

avg_daily_demand = avg_monthly_demand / 30

safety_stock = std_monthly_demand * 1.65

suggested_rop = (
    avg_daily_demand * lt_days
) + safety_stock

suggested_eoq = (
    eoq * 1.2
    if stockout_rate > 20
    else eoq * 0.9
)

o1, o2 = st.columns(2)

o1.metric(
    "Suggested ROP",
    round(suggested_rop, 2)
)

o2.metric(
    "Suggested EOQ",
    round(suggested_eoq, 2)
)

# =========================================================
# STOCK EVOLUTION CHART
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Stock Evolution
</h3>
""", unsafe_allow_html=True)

fig1, ax1 = plt.subplots(figsize=(14, 5))

ax1.plot(
    demand_df["Date"],
    demand_df["Stock_After"],
    label="Stock"
)

ax1.plot(
    demand_df["Date"],
    demand_df["Demand"],
    label="Demand"
)

ax1.axhline(
    rop,
    linestyle="--",
    label="ROP"
)

ax1.legend()

st.pyplot(fig1)

# =========================================================
# ORDER TIMELINE
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Orders Timeline
</h3>
""", unsafe_allow_html=True)

orders_df = demand_df[
    demand_df["Order_Qty"] > 0
]

fig2, ax2 = plt.subplots(figsize=(14, 4))

ax2.bar(
    orders_df["Date"],
    orders_df["Order_Qty"]
)

st.pyplot(fig2)

# =========================================================
# DEMAND DISTRIBUTION
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Demand Distribution
</h3>
""", unsafe_allow_html=True)

fig3, ax3 = plt.subplots(figsize=(10, 4))

ax3.hist(
    demand_df["Demand"],
    bins=10
)

st.pyplot(fig3)

# =========================================================
# STOCKOUT MONTHS
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Stockout Months
</h3>
""", unsafe_allow_html=True)

stockout_df = demand_df[
    demand_df["Stockout"] == True
]

if not stockout_df.empty:

    stockout_display = stockout_df[
        ["Date", "Demand"]
    ].copy()

    stockout_display["Date"] = (
        stockout_display["Date"]
        .dt.strftime("%b-%Y")
    )

    st.dataframe(
        stockout_display,
        width="stretch"
    )

else:

    st.success("No stockout months detected.")

# =========================================================
# DETAILED TABLE
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Detailed Simulation Table
</h3>
""", unsafe_allow_html=True)

display_df = demand_df.copy()

display_df["Date"] = (
    display_df["Date"]
    .dt.strftime("%b-%Y")
)

def highlight_stockout(row):

    if row["Stockout"]:
        return [
            "background-color: #F8D7DA"
        ] * len(row)

    return [
        "background-color: #D4EDDA"
    ] * len(row)

styled_df = display_df.style.apply(
    highlight_stockout,
    axis=1
)

st.dataframe(
    styled_df,
    width="stretch",
    height=600
)

# =========================================================
# FINAL ASSESSMENT
# =========================================================

st.markdown("""
<h3 style='color:#3AAFA9; font-weight:700;'>
Overall Assessment
</h3>
""", unsafe_allow_html=True)

if criticality == "High":

    st.error("""
    This article presents a HIGH operational risk.
    Immediate inventory policy review is strongly recommended.
    """)

elif criticality == "Medium":

    st.warning("""
    Moderate inventory instability detected.
    Close monitoring recommended.
    """)

else:

    st.success("""
    Inventory policy appears stable and acceptable.
    """)