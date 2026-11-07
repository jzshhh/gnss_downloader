# GNSS Data Downloader

A free, portable, one-stop tool for batch-downloading GNSS data: IGS
observations and broadcast ephemerides, analysis center products (SP3, CLK,
ERP, SINEX, BIA, IONEX — Final/Rapid/Ultra-rapid), h-files (SOPAC, MIT), and
regional networks (Hong Kong SatRef built in).

**All download addresses are open, editable templates** (`{YYYY}`, `{DDD}`,
`{SSSS}` …) — when a data center rebuilds its site, you fix the URL yourself
instead of waiting for an update.

## Features

- Portable single exe, Chinese/English UI
- Five repositories: CDDIS, IGN, BKG, WHU, CODE(AIUB); user-extensible
- RINEX 2/3 and pre/post long-name-reform handled automatically; MGEX (incl.
  BeiDou) supported
- Resume, skip-existing, missing/failed history, one-click retry
- Repository speed test; stations grouped by continent with map picker
- Earthdata account stored encrypted locally only

## Usage

Set the date range, check stations/products, press **Start**.
Data are saved to `rinex/…`, `product/<ac>/<series>/yyyy/ddd/`,
`hfile/<agency>/yyyy/`. See `User Manual.txt` for details.

## Build

```bat
pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "GNSS数据下载器" gnss_downloader.py
```

## Contact

Zhongshan Jiang, School of Geospatial Engineering and Science,
Sun Yat-sen University — jiangzhsh@mail.sysu.edu.cn
