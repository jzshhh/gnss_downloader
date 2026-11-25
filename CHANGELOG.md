# Changelog

## V1.2.1 — 2026-11-25

- Broadcast ephemerides: BRDC only (IGS combined long name or RINEX2 short name); BRDM/BRD4 and single-system nav are skipped. WHU web and WHU-FTP channels both kept.
- Repository paths verified end-to-end and fixed: SOPAC/IGN nav and ESA obs moved to day directories; MGEX weekly dirs were empty for all centers, so products are now read from the prod weekly dir; SOPAC IONEX (nonexistent) removed.
- Product tree narrowed to product types each AC actually publishes (verified against GPS week 2347); SINEX (SNX) removed from the default tree; empty MGEX nodes (COM/GBM) removed.
- Existing `sources.json` is upgraded automatically for all of the above.

## V1.2 — 2026-11-20

- Station table and map now use the official `IGSNetworkWithFormer.json` (776 stations); status is shown by `LastData` freshness.
- Data centers: the six IGS global centers plus WHU-FTP and the new CODE (AIUB) product center; "AIUB-specific products" renamed to "CODE-specific products".
- WHU web API now falls back to WHU-FTP for long-name RINEX 3 and d-files; download priority: long name > d-file > o-file, with d-files kept as-is.
- Downloads are verified (size, HTML error pages, gzip CRC); WHU `.gz` files are saved clean by stripping trailing HTML; external tools no longer open console windows.
- UI: fixed language switching, V1.2 title, SOPAC network field (MIT hidden), and taskbar icon.
