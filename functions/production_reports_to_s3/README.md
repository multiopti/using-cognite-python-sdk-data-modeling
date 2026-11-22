# production_reports_to_s3

Copies the hourly `Production Report` events from CDF to S3, so **Amazon Athena** can query them with SQL and
**Amazon Managed Grafana** can chart them and let users download them. The dashboard is
`grafana/dashboard_produccion_athena.json`.

```
hourly_production_report / shift_reconciler / plant_incident_sync ──► Production Report events (CDF)
   ──► this function (every 15 min) ──► s3://ingedaca-polar-production-data/production_hourly/...
   ──► Glue table polar_production.production_hourly ──► Athena (workgroup polar-grafana) ──► Grafana
```

## Output

One JSON Lines file per machine and shift, rewritten whole every time one of its hours changes:

```
s3://ingedaca-polar-production-data/production_hourly/shift_date=2026-11-19/shift=day/standum32.jsonl
```

One line per hour:

| Column | Meaning |
|---|---|
| `hour_start_utc` | Start of the hour, UTC. This is Grafana's time column. |
| `hour_start_local` | Start of the hour, plant time (UTC-4) |
| `hour_label`, `slot` | "6AM-7AM", 1..12 within the shift |
| `line`, `machine_type`, `machine` | L1/L3, DI/STANDUM/PRINTER/ISPRAY/MINSTER, code (e.g. `standum32`) |
| `production` | Cans produced in the hour (strokes for MINSTER) |
| `short_cans`, `trimmer_jams`, `cans_by_short_can`, `cans_by_trimmer_jam`, `downtime_by_short_can_min`, `downtime_by_trimmer_jam_min` | D&I / STANDUM |
| `downtime_min`, `efficiency_pct` | All machines |
| `scrap_kg`, `scrap_pct` | Scrap (merma), D&I / STANDUM |
| `retrac`, `blow_off` | PRINTER |
| `golpes_bobina`, `golpes_turno` | MINSTER |
| `observations` | The text the Reporte shows (automatic text, or the incident reported at the plant) |
| `incident_code`, `incident_source` | Set when the incident came from the plant (`plant_incident_sync`) |
| `event_external_id`, `event_last_updated_utc` | Traceability back to the CDF event |

The partitions in the path are `shift_date` and `shift`. A column that doesn't apply to a machine type is `null`.

**Behaviour:**
- **Scheduled run:** finds the events created or updated in the last 3 hours (`LOOKBACK_HOURS`) and rewrites their
  whole shifts. Corrections from `shift_reconciler` and incidents from `plant_incident_sync` reach S3 within about
  15 minutes.
- **Only changed files are uploaded:** the ETag is compared with the MD5 of the content. The bucket has versioning on,
  so an earlier version can always be recovered.

## `data` options

| Key | Default | Meaning |
|---|---|---|
| `dry_run` | `false` | Build everything, upload nothing. The result lists the files and a sample row. |
| `from`, `to` | — | Backfill: every shift with a shift date in `[from, to]` (`YYYY-MM-DD`). |
| `lookback_hours` | 3 | Window of the scheduled run. |
| `machines` | all | Only these machine codes. |

## Files

- `handler.py`, `config.py`, `requirements.txt`: the function. `config.MACHINES` is a copy of
  `hourly_production_report`'s machine list; `test_handler.py` checks it still matches.
- `test_handler.py`: offline tests with a fake CDF and a fake S3.
  ```
  E:\source\repos\streamlit\myenv\Scripts\python functions\production_reports_to_s3\test_handler.py
  ```
- `local_test.py`: runs against the real CDF project. It's a dry run unless `--write` is given; `--write` uploads with
  this PC's AWS CLI credentials.
- `athena_table.sql`: the Athena table (partition projection, so no `MSCK REPAIR` is needed).

## AWS resources (us-east-1, account 775232977034, created 2026-11-19)

| Resource | Notes |
|---|---|
| S3 `ingedaca-polar-production-data` | **Private**: all public access blocked, SSE-S3, versioning on. |
| S3 `grafana-athena-query-results-ingedaca-polar` | Athena results, private, expire after 7 days. The `grafana-athena-query-results-` prefix is required by Grafana's managed Athena policy. |
| Glue database `polar_production`, table `production_hourly` | `athena_table.sql` |
| Athena workgroup `polar-grafana` | Results go to the bucket above, enforced. 1 GB scan limit per query. Tag `GrafanaDataSource=true`, required by Grafana. |

The initial load (2026-07-28 to 2026-11-19) was run from this PC with `local_test.py`.

## Deploy (by hand in Fusion)

**Deployed 2026-11-22:** external id `production-reports-to-s3`, Python 3.14, schedule `every-15-min`. A catch-up run
with `{"from": "2026-11-20", "to": "2026-11-22"}` closed the gap after the manual load. If the function stops for longer
than `LOOKBACK_HOURS`, run it by hand with `from`/`to` for the missing shift dates.

1. **AWS credentials:** an IAM user just for this function, with only `s3:PutObject`, `s3:GetObject` and `s3:ListBucket`
   on `ingedaca-polar-production-data`. Put its keys in the Function's secrets `aws-access-key` and `aws-secret-key`.
   Same names as `shift-excel-report-v2`; Fusion only accepts short, lowercase names with dashes.
2. **Create the Function:** upload a zip with `handler.py`, `config.py` and `requirements.txt`. External id
   `production-reports-to-s3`.
3. **First run by hand** with `{"dry_run": true}`, then with `{}`.
4. **Schedule:** every 15 minutes, `*/15 * * * *`, data `{}`.

Cognite Functions can't be updated in place: deploy a fix as `-v2` and retire the old one.

## Grafana

- **Workspace role permissions (done 2026-11-19).** The inline policy `AthenaPolarProduction`
  (`grafana_role_policy.json`) is on `AmazonGrafanaServiceRole-fSS550tbr`, the role of workspace `g-be0abff680`. It
  allows:
  - Athena queries only in workgroup `polar-grafana`;
  - Glue read only on `polar_production`;
  - S3 read only on `production_hourly/`;
  - read/write on the results bucket.

  Checked with the IAM policy simulator: other workgroups, other Glue databases, writes to the data bucket and other
  buckets are denied. AWS's broader `AmazonGrafanaAthenaAccess` is deliberately NOT used, because the workspace is
  shared with other clients.
- **Data source (to do in Grafana):** Amazon Athena, authentication "Workspace IAM Role", region us-east-1, catalog
  `AwsDataCatalog`, database `polar_production`, workgroup `polar-grafana`.
- Import `grafana/dashboard_produccion_athena.json` into a folder that only Empresas Polar users can see.
