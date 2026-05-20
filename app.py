import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Inventory Simulation Dashboard",
    layout="wide"
)

st.markdown(
    "<h1 style='color:#31859C; font-size:38px; font-weight:700;'>"
    "Inventory Simulation Dashboard"
    "</h1>",
    unsafe_allow_html=True
)

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
        'janv': 'Jan', 'févr': 'Feb', 'mars': 'Mar', 'avr': 'Apr',
        'mai': 'May', 'juin': 'Jun', 'juil': 'Jul', 'août': 'Aug',
        'sept': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'déc': 'Dec'
    }

    def parse_french_month(x):
        x = str(x).lower()
        for fr, en in month_map.items():
            x = x.replace(fr, en)
        return pd.to_datetime(x, format='%b-%y')

    cons['Date'] = cons['Month'].apply(parse_french_month)
    cons.rename(columns={'Valeur': 'Consumption'}, inplace=True)

    return params, cons

params, cons = load_data()

# =========================================================
# REQUIRED COLUMNS
# =========================================================

COL_ROP = 'Reorder Point (ROP) (m2: Monthly)'
COL_EOQ = 'EOQ (Economic Order Quantity)'
COL_LT = 'Lead Time (Days)'

# =========================================================
# PIVOT
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

st.sidebar.header("🔎 Search Article")

article_list = params['Article'].astype(str).tolist()

selected_article = st.sidebar.selectbox(
    "Select article",
    article_list
)

# =========================================================
# GET ARTICLE ROW
# =========================================================

row = params[params['Article'].astype(str) == selected_article]

if row.empty:
    st.error("Article not found")
    st.stop()

row = row.iloc[0]

# =========================================================
# HEADER
# =========================================================

st.markdown(
    "<h3 style='color:#3AAFA9; font-weight:700;'>Article Information</h3>",
    unsafe_allow_html=True
)

c1, c2, c3, c4 = st.columns(4)

c1.metric("Article", selected_article)
c2.metric("ABC", row['ABC'])
c3.metric("HML", row['HML'])
c4.metric("XYZ", row['XYZ classification'])

st.info(str(row['Désignation article']))

# =========================================================
# PARAMETERS
# =========================================================

rop = float(row[COL_ROP])
eoq = float(row[COL_EOQ])
lt_days = float(row[COL_LT])

lt_months = max(1, math.ceil(lt_days / 30))

p1, p2, p3 = st.columns(3)

p1.metric("ROP", round(rop, 2))
p2.metric("EOQ", round(eoq, 2))
p3.metric("Lead Time (Months)", lt_months)

# =========================================================
# DEMAND
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
    "Demand": art_series.values
})

demand_df["Demand"] = demand_df["Demand"].abs()

# =========================================================
# INVENTORY SIMULATION
# =========================================================

stock = rop + (eoq / 2) if eoq > 0 else rop * 2

on_order = {}
last_order_month = -999

stock_before_list = []
received_list = []
stock_after_list = []
stock_after_receipt_list = []
order_qty_list = []
stockout_list = []

unfilled_demand = 0

for i, demand in enumerate(demand_df["Demand"]):

    # 1. RECEIVE ORDERS
    received = on_order.pop(i, 0)
    stock += received

    stock_before = stock

    # 2. APPLY DEMAND
    stock_raw = stock - demand

    in_stockout = stock_raw < 0

    if in_stockout:
        unfilled_demand += abs(stock_raw)
        stock = 0
    else:
        stock = stock_raw

    # 3. ORDER LOGIC
    months_since_last = i - last_order_month
    can_order = True if in_stockout else (months_since_last >= lt_months)

    order_qty = 0

    if stock <= rop and eoq > 0 and can_order:

        arrival = i + lt_months

        if arrival < len(demand_df):
            on_order[arrival] = on_order.get(arrival, 0) + eoq

        last_order_month = i
        order_qty = eoq

    # 4. STORE
    stock_before_list.append(stock_before)
    received_list.append(received)
    stock_after_list.append(stock)

    stock_after_receipt_list.append(stock_before + received - demand)

    order_qty_list.append(order_qty)
    stockout_list.append(in_stockout)

# =========================================================
# DATAFRAME
# =========================================================

demand_df["Stock_After"] = stock_after_list
demand_df["Stock_After_With_Receipts"] = stock_after_receipt_list
demand_df["Order_Qty"] = order_qty_list
demand_df["Order_Placed"] = demand_df["Order_Qty"] > 0
demand_df["Stockout"] = stockout_list

# =========================================================
# KPIs
# =========================================================

total_stockouts = sum(stockout_list)
total_demand = demand_df["Demand"].sum()
fill_rate = (1 - unfilled_demand / max(total_demand, 1)) * 100
total_orders = sum(demand_df["Order_Qty"] > 0)

st.markdown(
    "<h3 style='color:#3AAFA9; font-weight:700;'>Simulation Results</h3>",
    unsafe_allow_html=True
)

k1, k2, k3 = st.columns(3)

k1.metric("Stockout Months", total_stockouts)
k2.metric("Fill Rate %", round(fill_rate, 2))
k3.metric("Orders Placed", total_orders)

# =========================================================
# CHARTS
# =========================================================

st.markdown("<h3 style='color:#3AAFA9;'>Stock Evolution</h3>", unsafe_allow_html=True)

fig, ax = plt.subplots(figsize=(14, 5))
ax.plot(demand_df["Date"], demand_df["Stock_After"])
ax.axhline(rop, linestyle="--")
ax.grid(False)
st.pyplot(fig)

# =========================================================
# TABLE WITH COLORS
# =========================================================

st.markdown(
    "<h3 style='color:#3AAFA9; font-weight:700;'>Simulation Table</h3>",
    unsafe_allow_html=True
)

display_df = demand_df.copy()
display_df["Date"] = display_df["Date"].dt.strftime("%b-%Y")

# ⭐ COLOR LOGIC
def highlight_stock(col):
    return [
        "background-color: #F8D7DA" if v < rop else "background-color: #D4EDDA"
        for v in col
    ]

styled_df = display_df.style.apply(highlight_stock, subset=["Stock_After"])

st.dataframe(styled_df, width="stretch")