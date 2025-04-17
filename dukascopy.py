from datetime import datetime, timezone
import requests
import lzma
import struct
import pandas as pd
import io
import os
from dotenv import load_dotenv
import pygsheets
import ta  # A 'ta' könyvtárat használjuk indikátorokhoz (pip install ta)

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
        for hour in range(start - 2,start + 2):
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

                        base_timestamp = int(datetime(year, date.month, day, hour, tzinfo=timezone.utc).timestamp())

                        df = pd.DataFrame(data, columns=['Timestamp', 'Ask', 'Bid', 'VolumeAsk', 'VolumeBid'])
                        df['DateTime'] = pd.to_datetime(base_timestamp + (df["Timestamp"] / 1000), unit='s', utc=True)
                        df["Ask"] = df["Ask"] / 100000
                        df["Bid"] = df["Bid"] / 100000
                        df["MidPrice"] = (df["Ask"] + df["Bid"]) / 2

                        # Külön DateTime oszlop és index beállítása
                        df['DateTime'] = df['DateTime']  # Megőrizzük a DateTime oszlopot
                        df.set_index('DateTime', inplace=True)  # Az index is marad DateTime

                        # OHLC és volume aggregálás percre bontva
                        df_ohlc = df['MidPrice'].resample('min').ohlc()
                        df_volume = df['VolumeAsk'].resample('min').sum()

                        # OHLC és volume kombinálása
                        df_combined = pd.concat([df_ohlc, df_volume], axis=1)
                        df_combined.columns = ['open', 'high', 'low', 'close', 'volume']

                        # A DateTime oszlopot visszamentjük az egyesített DataFrame-be
                        df_combined['DateTime'] = df_combined.index

                        all_data.append(df_combined)

                        
                    else:
                        print(f"Nincs adat: {url}")
                    break  # Ha sikerült vagy nincs adat, ne próbálkozzunk újra

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

nfp_eurusd = download_dukascopy("EURUSD", nfp_dates)

