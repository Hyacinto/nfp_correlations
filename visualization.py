import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit as st
import seaborn as sns

# Data load
nfp_data = pd.read_csv("PAYEMS.csv")
nfp_data.rename(columns={"PAYEMS": "NFP"}, inplace=True)

sheet_id = "1gssv0EhPRkNiZiTkxRMyUwgC0PZHiDHN5C6bImVRJvA"

# Csak az első oszlop beolvasása
nfp_dates = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv", delimiter=",", usecols=[0,1], header=None, names=["Date","Time"])

# Dátumformátum konvertálása
nfp_dates["Date"] = pd.to_datetime(nfp_dates["Date"].str.extract(r'([A-Za-z]{3} \d{2}, \d{4})')[0], format="%b %d, %Y")

nfp_dates["Time"] = nfp_dates["Time"].str.replace(":30","").astype(int)

nfp_changes = nfp_data["NFP"].diff() # NFP változások

nfp_percentage_changes = nfp_data["NFP"].diff(-1) / nfp_data["NFP"] * 100 # NFP százalékos változások

USDJPY = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=680374855", delimiter=",")

USA500IDXUSD = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=302875650", delimiter=",")

BTCUSD = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=1434109159", delimiter=",")

XAUUSD = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=1857249717", delimiter=",")

BRENTCMDUSD = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=1783071987", delimiter=",")

EXPECTATION_VS_ACTUAL = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv", delimiter=",", usecols=[2,3], header=None, names=["Actual","Expectation"])

closing_to_the_expectation = (EXPECTATION_VS_ACTUAL["Actual"].str.replace(',', '').str.replace('K', '').astype(float) - EXPECTATION_VS_ACTUAL["Expectation"].str.replace(',', '').str.replace('K', '').astype(float)) / EXPECTATION_VS_ACTUAL["Expectation"].str.replace(',', '').str.replace('K', '').astype(float) * 100

coolwarm_data = pd.concat( [USDJPY["diff_highest"], 
                           USA500IDXUSD["diff_highest"], 
                           BTCUSD["diff_lowest"] * -1, 
                           XAUUSD["diff_lowest"] * -1, 
                           BRENTCMDUSD["diff_lowest"] * -1, 
                           nfp_percentage_changes,
                           closing_to_the_expectation
                           ],
                           axis=1)

# Reindexelés az NFP dátumokhoz, hogy minden NFP dátum szerepeljen
coolwarm_data = coolwarm_data.reindex(nfp_dates.index)

# Kitöltjük a hiányzó értékeket az előző elérhető adattal (forward fill)
#coolwarm_data = coolwarm_data.ffill()

coolwarm_data = coolwarm_data.dropna()

coolwarm_data.columns = ["USDJPY","USA500IDXUSD","BTCUSD", "XAUUSD", "BRENTCMDUSD", "NFP", "Expectation" ]

# Korrelációs mátrix kiszámítása
correlation_matrix = coolwarm_data.corr()

# Streamlit felület
st.title("NFP and corrleations")
st.write("Impact of the NFP announcement on trade")

# Hőtérkép megjelenítése
fig, ax = plt.subplots(figsize=(8, 6))  # Hőtérkép méretének beállítása
sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', ax=ax)

# A hőtérkép megjelenítése Streamlit-ben
st.pyplot(fig)

# Recessions dates 
recessions = [
    {"event": "World War II", "start": "1939-09-01", "end": "1945-05-08"},
    {"event": "1953 Recession", "start": "1953-07-01", "end": "1954-05-01"},
    {"event": "1973-1975 Oil Crisis and Recession", "start": "1973-10-01", "end": "1975-03-01"},
    {"event": "1980-1982 Recession", "start": "1980-01-01", "end": "1982-11-01"},
    {"event": "1990-1991 Recession", "start": "1990-07-01", "end": "1991-03-01"},
    {"event": "2001 Recession (Dot-com Bubble Burst)", "start": "2001-03-01", "end": "2001-11-01"},
    {"event": "2007-2009 Global Financial Crisis (Great Recession)", "start": "2007-12-01", "end": "2009-06-01"},
    {"event": "COVID-19 Recession", "start": "2020-02-01", "end": "2020-04-01"},
    {"event": "2022 Inflation Crisis (Post-COVID)", "start": "2022-03-01", "end": "2024-12-01"}
]

positive_events = [
    {"event": "Post-WWII Economic Boom", "start": "1945-05-08", "end": "1960-01-01"},
    {"event": "The 1980s Recovery and Expansion (Reagan Era)", "start": "1983-11-01", "end": "1990-07-01"},
    {"event": "1990s Economic Expansion (Clinton Era)", "start": "1991-03-01", "end": "2001-03-01"},
    {"event": "2009-2020 Recovery (Post-Great Recession)", "start": "2009-06-01", "end": "2020-02-01"},
    {"event": "Post-COVID Recovery", "start": "2021-01-01", "end": "2022-03-01"}
]

# Presidents and their inauguration dates

presidents = pd.read_csv("us_presidents.csv")

# Konvertáljuk a dátumot numerikus értékekre a trendvonalhoz
nfp_data["observation_date"] = pd.to_datetime(nfp_data["observation_date"])
nfp_data["DATE_NUM"] = nfp_data["observation_date"].map(pd.Timestamp.toordinal) # Dátum numerikus értéke

# Trendvonal számítása
z = np.polyfit(nfp_data["DATE_NUM"], nfp_data["NFP"], 1)  # 1. fokú polinom (lineáris trend)
p = np.poly1d(z)  # Polinom függvény létrehozása
nfp_data["TREND"] = p(nfp_data["DATE_NUM"])  # Trendvonal értékei

# Make Diagram

# Létrehozunk egy üres grafikont
fig = go.Figure()

# Hozzáadjuk az NFP és trendvonalat
fig.add_trace(go.Scatter(
    x=nfp_data["observation_date"], y=nfp_data["NFP"], 
    mode="lines", name="NFP data", line=dict(color="blue"),
    legendgroup="nfp",  # Csoportosítható
    visible=True  # Mindig látszik
    ))

fig.add_trace(go.Scatter(
    x=nfp_data["observation_date"], y=nfp_data["TREND"],
    mode="lines", name="Trendline", line=dict(color="green", dash="dash"),
    legendgroup="trend",  # Csoportosítható
    visible=True  # Mindig látszik                                       
    ))

# Recessziók kiemelése
for event in recessions:
    fig.add_trace(go.Scatter(
        x=[event["start"], event["end"], event["end"], event["start"], event["start"]],
        y=[nfp_data["NFP"].min(), nfp_data["NFP"].min(), nfp_data["NFP"].max(), nfp_data["NFP"].max(), nfp_data["NFP"].min()],
        fill="toself",
        fillcolor="red", opacity=0.3, line_width=0,
        name=event["event"], legendgroup="recessions",
        visible="legendonly"
    ))

# Pozitív események kiemelése
for event in positive_events:
    fig.add_trace(go.Scatter(
        x=[event["start"], event["end"], event["end"], event["start"], event["start"]],
        y=[nfp_data["NFP"].min(), nfp_data["NFP"].min(), nfp_data["NFP"].max(), nfp_data["NFP"].max(), nfp_data["NFP"].min()],
        fill="toself",
        fillcolor="green", opacity=0.3, line_width=0,
        name=event["event"], legendgroup="positive",
        visible="legendonly"
    ))

# Elnökök kiemelése
president_names = presidents["president"].tolist()
president_dates = pd.to_datetime(presidents["start"].tolist())

for president, date in zip(president_names, president_dates):
    if date.year >= 1939:
        fig.add_trace(go.Scatter(
        x=[date, date], y=[nfp_data["NFP"].min(), nfp_data["NFP"].max()],
        mode="lines", line=dict(color="red", dash="dash"),
        name=president, legendgroup="presidents",
        visible="legendonly"
    ))
        
# Címek, címkék és egyéb beállítások
fig.update_layout(
    title="NFP Data and Historical Events",
    xaxis_title="Date",
    yaxis_title="All Employees, Total Nonfarm (thousands)",
    showlegend=True,
    xaxis_rangeslider_visible=True,
    template="plotly_dark"
)

# Megjelenítjük a grafikont a Streamlit alkalmazásban
st.plotly_chart(fig)







