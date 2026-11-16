# powerbi/

Power BI Desktop assets for the Lumi Accessories France dashboard (simulated data, MySQL warehouse `lumi_dw`).

> **WARNING: the TMDL model in `model/` is UNTESTED.** It was written without access to Power BI Desktop, from knowledge of the TMDL syntax. It may fail to open or need small fixes. Uncertain spots are marked with `annotation TODO_verify` lines in the `.tmdl` files. The reliable path is `SETUP.md` + `measures.dax`.

## Status

| File | Status |
|---|---|
| `measures.dax` | Reliable: calculated columns and 37 measures with formats and display folders, ready to paste. Not executed against a live model here, but names follow `build_dw.py` and `docs/10-dashboard-spec.md`. |
| `SETUP.md` | Reliable: step-by-step build (driver, MySQL connection, relationships, 4 pages, reconciliation numbers). |
| `model/` | Untested TMDL semantic model (best effort). |

## Layout of `model/`

```
model/
  definition.pbism          # semantic model settings (version 4.0)
  definition/
    database.tmdl
    model.tmdl
    relationships.tmdl      # 6 active + 1 inactive (dim_customer.first_date_key -> dim_date.date_key)
    tables/                 # one .tmdl per table: columns, types, keys, measures (_Measures), M partitions
```

`tables/_Measures.tmdl` and the calculated columns are generated from `measures.dax`; if you edit DAX, edit `measures.dax` first and keep the TMDL in sync.

## Try opening the TMDL model

1. Power BI Desktop > File > Options and settings > Options > Preview features: enable **Power BI Project (.pbip) save option** and **Store semantic model using TMDL format**. Restart.
2. Create a blank report and **Save as** a `.pbip` (e.g. `Lumi.pbip`). Desktop creates `Lumi.pbip`, `Lumi.Report/` and `Lumi.SemanticModel/`. Close Desktop.
3. Copy the contents of `powerbi/model/` (`definition.pbism` and the `definition/` folder) into `Lumi.SemanticModel/`, replacing what is there.
4. Open `Lumi.pbip`. Desktop asks for MySQL credentials (Database tab, user `lumi`). Then Refresh.
5. If it fails, read the error: it names the file and line. Fix or delete the offending property and retry. Known doubtful points: `dataCategory: Time` + `isKey` on `dim_date[full_date]`, the calculated-table partitions (`_Measures`, `waterfall_steps`), unquoted `€` in format strings.

## Fallback

Ignore `model/` and follow `SETUP.md` (about 30 minutes by hand, fully reliable). Passwords are never stored in these files: the M partitions only contain host `127.0.0.1` and database `lumi_dw`.
