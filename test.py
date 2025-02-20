from datetime import datetime, timezone
import requests
import lzma
import struct
import pandas as pd
import io
import os
from dotenv import load_dotenv
import pygsheets

sheet_id = "1gssv0EhPRkNiZiTkxRMyUwgC0PZHiDHN5C6bImVRJvA"

nfp_dates = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv", delimiter=",", usecols=[0,1], header=None, names=["Date","Time"])

# Dátumformátum konvertálása
nfp_dates["Date"] = pd.to_datetime(nfp_dates["Date"].str.extract(r'([A-Za-z]{3} \d{2}, \d{4})')[0], format="%b %d, %Y")
nfp_dates["Time"] = nfp_dates["Time"].str.replace(":30","").astype(int)

# UTC időzóna hozzáadása

def get_daylight_savings_time(year):
    # A második vasárnap márciusban
    march_first = pd.Timestamp(year=year, month=3, day=1)
    march_second_sunday = march_first + pd.DateOffset(weeks=1, weekday=pd.offsets.Week(weekday=6))

    # Az első vasárnap novemberben
    november_first = pd.Timestamp(year=year, month=11, day=1)
    november_first_sunday = november_first + pd.DateOffset(weekday=pd.offsets.Week(weekday=6))

    return march_second_sunday, november_first_sunday

def convert_start_to_UTC(row):
    march_second, november_first_sunday = get_daylight_savings_time(row["Date"].year)
    # Nyári időszámítás esetén +5, téli esetén +4
    return row["Time"] + (5 if march_second <= row["Date"] < november_first_sunday else 4)

# Alkalmazzuk a konverziót minden sorra:
nfp_dates["Time"] = nfp_dates.apply(convert_start_to_UTC, axis=1)


def download_dukascopy(symbol, dates, max_retries=3):
    base_url = "https://datafeed.dukascopy.com/datafeed"
    all_data = []

    for _, row in dates.iterrows():
        date = row["Date"]
        year = date.year
        month = date.month - 1  # Dukascopy hónapok: január = 00, február = 01, stb.
        day = date.day

        if year < 2003:  # A Dukascopy adatok csak 2003-tól érhetőek el
            #print(f"Nincs elérhető adat {date}-ra. Kihagyva...")
            continue

        start = row['Time']

        # Az NFP utáni 2 óra adatainak letöltése
        for hour in range(start, start + 2):
            url = f"{base_url}/{symbol}/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
            print(f"Downloading: {url}")

            retries = 0
            while retries < max_retries:
                    response = requests.get(url)   
                    if response.status_code == 200 and len(response.content) > 0:
                        fmt = '>3I2f'
                        data = []
                        
                        chunk_size = struct.calcsize(fmt)
                        decompressed_data = lzma.decompress(response.content)
                        with io.BytesIO(decompressed_data) as f:
                            while True:
                                chunk = f.read(chunk_size)
                                if chunk:
                                    data.append(struct.unpack(fmt, chunk))
                                else:
                                    break

                        base_timestamp = int(datetime(year, date.month, day,hour, tzinfo=timezone.utc).timestamp())

                        df = pd.DataFrame(data, columns=['Timestamp', 'Ask', 'Bid', 'VolumeAsk', 'VolumeBid'])
                        df['DateTime'] = pd.to_datetime(base_timestamp + (df["Timestamp"] / 1000), unit='s', utc=True)
                        if symbol == "USA500IDXUSD":
                            df["DateTime"] = df["DateTime"].dt.floor("s")  # Másodpercre kerekítés
                        df["Ask"] = df["Ask"] / 100000
                        df["Bid"] = df["Bid"] / 100000
                        df["MidPrice"] = (df["Ask"] + df["Bid"]) / 2

                        all_data.append(df)
                        
                    else:
                        print(f"Nincs adat: {url}")
                    break  # Ha sikerült vagy nincs adat, ne próbálkozzunk újra

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def prices_from_an_intervall(df, dates):

    df_dates = df["DateTime"].dt.date
    dates["Date"] = pd.to_datetime(dates["Date"]).dt.date
    dates = dates[dates["Date"].isin(df_dates)]

    prices_from_an_interval = []

    for _, row in dates.iterrows():
        date = row["Date"]
        start = row["Time"]
       
        start_time = pd.Timestamp(f"{date} {start}:30:00", tz="UTC")
   
        end_time = pd.Timestamp(f"{date} {start + 1}:30:00", tz="UTC")
  
        df_interval = df[(df["DateTime"] >= start_time) & (df["DateTime"] <= end_time)]

        if df_interval.empty :
            continue

        data = {}
        data["OpenPrice"] = df_interval["MidPrice"].iloc[0]
        data["LowestPrice"] = df_interval["MidPrice"].min()
        data["HighestPrice"] = df_interval["MidPrice"].max()
        data["ClosePrice"] = df_interval["MidPrice"].iloc[-1]
        data['diff_lowest'] = ((data['LowestPrice'] - data['OpenPrice']) / data['OpenPrice']) * 100
        data['diff_highest'] = ((data['HighestPrice'] - data['OpenPrice']) / data['OpenPrice']) * 100
        data["Date"] = row["Date"]

        one_interval = pd.DataFrame([data])
        prices_from_an_interval.append(one_interval)
    
    return pd.concat(prices_from_an_interval, ignore_index=True)

tickers = ["USDJPY","BTCUSD", "XAUUSD", "BRENTCMDUSD", "USA500IDXUSD"]

for ticker in tickers:

    all_price_from_two_hours = download_dukascopy(ticker,nfp_dates)

    nfp_prices = prices_from_an_intervall(all_price_from_two_hours, nfp_dates)

    load_dotenv()

    GOOGLE_SERVICE_ACCOUNT_KEY_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH")

    gc = pygsheets.authorize(service_file=GOOGLE_SERVICE_ACCOUNT_KEY_PATH)
 
    sh = gc.open("NFP Data")
 
    sh.add_worksheet(ticker)
 
    index = len(sh.worksheets())
 
    wks = sh[index-1]
 
    wks.set_dataframe(nfp_prices, (1, 1))