# gnss_downloader
A free, portable, one-stop tool for batch-downloading GNSS data: IGS observations and broadcast ephemerides, analysis center products (SP3, CLK, ERP, SINEX, BIA, IONEX — Final/Rapid/Ultra-rapid), h-files (SOPAC, MIT), and regional networks (Hong Kong SatRef built in).

All download addresses are open, editable templates ({YYYY}, {DDD}, {SSSS} …) — when a data center rebuilds its site, you fix the URL yourself instead of waiting for an update.

# Features
- Portable single exe, Chinese/English UI
- Six IGS global data centers (CDDIS, ESA GSSC, SOPAC, WHU, IGN, KASI) + WHU-FTP dual channel + CODE (AIUB) product center; station list from official IGSNetworkWithFormer.json (776 stations); user-extensible
- Analysis centers aligned with the official IGS ACC list; station status from IGSNetworkWithFormer.json
- RINEX 2/3 and pre/post long-name-reform handled automatically; MGEX (incl. BeiDou) supported
  Resume, skip-existing, missing/failed history, one-click retry
- Repository speed test; stations grouped by continent with map picker
- Earthdata account stored encrypted locally only

# Build
```bat
python -m PyInstaller --noconfirm --onefile --windowed --icon=gnss.ico --name gnss_downloader --add-data "leaflet;leaflet" --add-data "gnss.ico;." --add-data "gzip.exe;." --add-data "crx2rnx.exe;."  --add-data "User Manual.txt;." --add-data "使用说明.txt;." gnss_downloader.py
```

# Usage
Set the date range, check stations/products, press Start. Data are saved to rinex/…, product/<ac>/<series>/yyyy/ddd/, hfile/<agency>/yyyy/. See User Manual.txt for details.

# Contact
Author Zhongshan Jiang, School of Geospatial Engineering and Science, Sun Yat-sen University 

E-mail: jiangzhsh@mail.sysu.edu.cn
