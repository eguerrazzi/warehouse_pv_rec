# Data sources

Generated from the `*.meta.yaml` sidecars in `data/processed/` by `wpvrec data sources`;
do not edit by hand. Raw files live in `data/raw/` (not committed) and are recreated by
`wpvrec data download`.

| Processed file | Source | Licence | Retrieved | Raw SHA-256 | Source type |
|---|---|---|---|---|---|
| `calendar_2025.csv` | Italian national public holidays, 2025 (Law 260/1949 as amended) | public law | computed | — | derived |
| `elmas_shapes.csv` | ELMAS dataset (Bellinguer et al. 2023), Time_series_18_clusters.csv, France 2018 | CC BY 4.0 (Bellinguer, Girard, Bocquet, Chevalier 2023) | 2026-11-18 | f91914f92418… | real |
| `household_profile.csv` | Bottom-up from Nazemi et al. (2021) Buildings 11(6) 237, Table 1 (appliances, times, durations) and Cruz et al. (2019) Sensors 19(18) 3973, Table 2 (rated powers, stand-by), as in Mariuzzo et al. (2023) IJEPES 153:109331 | values transcribed from CC BY 4.0 papers (MDPI) | 2026-11-18 | — | derived |
| `prices_cnor_2025.csv` | GME, MGP zonal prices, zone CNOR, year 2025 (file *_60.xlsx, sheet Prezzi-Prices) | GME terms of use (www.mercatoelettrico.org, 'Condizioni generali di utilizzo'); raw files not redistributed, aggregated profiles only | 2026-11-18 | 62e10d5c2c11… | real |
| `pv_control_year.csv` | PVGIS v5.3 (JRC), seriescalc, PVGIS-SARAH3 | PVGIS (c) European Union, 2001-2026; reuse authorised with acknowledgement (Commission Decision 2011/833/EU) | 2026-11-18 | 15005f812315… | real |
| `pv_typical_year.csv` | PVGIS v5.3 (JRC), seriescalc, PVGIS-SARAH3 | PVGIS (c) European Union, 2001-2026; reuse authorised with acknowledgement (Commission Decision 2011/833/EU) | 2026-11-18 | 15005f812315… | real |

## Processing steps

### `calendar_2025.csv`

- URL: https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1949-05-27;260
- Mon-Fri minus national holidays (Easter Monday from the Gregorian computus)
- patron-saint holiday not included

### `elmas_shapes.csv`

- URL: https://doi.org/10.6084/m9.figshare.23889780 (file https://ndownloader.figshare.com/files/41895786)
- UTC timestamps (no DST gaps) converted to Europe/Rome local time
- each cluster normalised to its 2018 annual energy
- mean by (cluster, month, day type, slot); day type from the French 2018 calendar

### `household_profile.csv`

- URL: data/manual/household_appliances.csv
- power source cruz, timing preferred, minute resolution, hourly slots (local time)
- non-working days: chores uniform 9-19 h, extra stove use at 12.5 h
- base load 1.094 kWh/day (fridge 322 kWh/yr + stand-by), not scaled
- appliance energy x 0.315 so that the calendar year gives 2700 kWh
- same profile in every month (no seasonal data in the sources)

### `prices_cnor_2025.csv`

- URL: https://www.mercatoelettrico.org/it-it/Home/Esiti/Elettricita/MGP/Statistiche/DatiStorici/moduleId/10874/controller/GmeDatiStoriciItem/action/DownloadFile?fileName=Anno2025.zip
- Ora 1..24 = local slot t; 25th hour of the DST day dropped
- Oct-Dec values are GME hourly re-elaborations of 15-minute prices
- mean by (month, day type, slot); day type from the Italian 2025 calendar

### `pv_control_year.csv`

- URL: https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat=43.1668&lon=11.7716&startyear=2005&endyear=2023&pvcalculation=1&peakpower=1&loss=14&mountingplace=free&aspect=0&outputformat=json&optimalinclination=1
- UTC hourly PVGIS values (W per kWp) converted to Europe/Rome local time
- mean over the days of 2023 for each (month, slot): the control year

### `pv_typical_year.csv`

- URL: https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat=43.1668&lon=11.7716&startyear=2005&endyear=2023&pvcalculation=1&peakpower=1&loss=14&mountingplace=free&aspect=0&outputformat=json&optimalinclination=1
- UTC hourly PVGIS values (W per kWp) converted to Europe/Rome local time
- mean over all days of 2005-2023 for each (month, slot): the 'typical year'
- rows = month 1-12, columns = slot 1-24

