# plant_incident_sync

Writes the hourly incidents operators report in the plant's Reporte de Producción to the `Production Report`
events in CDF. The incident text goes in the `observations` field that Fusion shows. Runs every 5 minutes; a report
reaches CDF within about 5–10 minutes.

```
Reporte (plant) → Node-RED → Optix matrices Model/OBSERVACIONES
  → Optix NetLogic IncidentSnapshot (every 60 s) → MQTTPublisherIncidents (every 5 min, existing AWS IoT connection)
  → AWS IoT Core, topic SuperenvasesIncidents/snapshot
  → CDF hosted extractor job (MQTT_AWS_July2026) → RAW db_superenvases_raw.raw_incident_snapshots
  → this function → Production Report events
```

## What it does

Each run reads the newest snapshot in RAW. It only uses one sent in the last 30 minutes (`MAX_AGE_MINUTES`): with
no recent snapshot, because the plant is offline, it does nothing, and the next snapshot after the outage brings
everything up to date. Each snapshot holds every incident of the last 7 days.

For each reported hour:
- **Event found:** if its `observations` text or `incident_code` differ from the report, it adds to the metadata
  `observations` and `observaciones` (the incident text), `incident_code`, `incident_source=plant` and
  `incident_synced_at`. Everything else in the event stays as it is.
- **Already up to date:** nothing is written, so re-runs are harmless.
- **No event yet** (hourly_production_report hasn't run for that hour): it waits for a later run. It never creates
  events.
- **hourly_production_report re-ran the hour** and put its automatic text back: the next run restores the incident.

Rules agreed with the client:
- Incidents are only reported, never cleared. Every code is written, including 0 "Operación estándar", and a newer
  code replaces the old one.
- Hours where nothing was reported are never touched, so observations entered earlier in Fusion stay.
- The plant is the only place incidents are entered: incident editing in Fusion is turned off when this ships.

## Files

- `handler.py`: the function.
- `config.py`: RAW table, maximum snapshot age, and two **copies** that must stay in sync (Cognite Functions can't
  import from other folders):
  - `INCIDENTES_OPCIONES`, from `streamlit/config.py`. Append-only: when an option is added there, append it here
    too and redeploy. Until then, hours with the new code are reported as skipped.
  - `OBS_KEY_TO_CODE`: Optix machine key → machine code of `hourly_production_report`.
- `test_handler.py`: offline tests with a fake CDF client. They also check that both copies still match.
  ```
  E:\source\repos\streamlit\myenv\Scripts\python functions\plant_incident_sync\test_handler.py
  ```
- `local_test.py`: dry run against the real CDF project (reads only, writes nothing).
  ```
  E:\source\repos\streamlit\myenv\Scripts\python functions\plant_incident_sync\local_test.py
  ```

## `data` options

| Key | Default | Meaning |
|---|---|---|
| `dry_run` | `false` | Compute everything, write nothing. The result lists what would change. |
| `machines` | all | Only these machine codes, e.g. `["di11"]`. |
| `snapshot` | read RAW | Use this snapshot (dict or JSON text) instead of RAW. For tests. |
| `max_age_minutes` | 30 | Override `MAX_AGE_MINUTES`. |

## Deploy (by hand in Fusion)

The `.env` service account can't create Functions, so this is done in Fusion. Cognite Functions can't be updated in
place: deploy a fix as a new function (e.g. `plant-incident-sync-v2`) and retire the old one.

1. **Before the function:**
   - the Optix publisher is running at the plant;
   - the table `raw_incident_snapshots` exists in `db_superenvases_raw` (Integrate › Staging);
   - the hosted extractor job exists (see `cognite-sdk/TODO.md`: topic `SuperenvasesIncidents/#`, same code as the
     existing job with `"table": "raw_incident_snapshots"`).
   - Check that rows arrive in the table, one every 5 minutes.
2. **Create the function:** Build solutions › Functions › Upload a zip with `handler.py`, `config.py` and
   `requirements.txt`. External id `plant-incident-sync`.
3. **First run by hand** with `{"dry_run": true}`. Then `{"machines": ["di11"]}`, check the event in Fusion, and only
   then the schedule.
4. **Schedule:** every 5 minutes, cron `*/5 * * * *`, data `{}`. Like the other functions' schedules, it needs a
   service account with:
   - RAW read on `db_superenvases_raw`;
   - Events read and write on the data set of the Production Report events (`5144187181631371`).
5. **Same release:** deploy the Fusion Reporte in read-only mode (incident editing off).

The result of each run shows `updated`, `up_to_date`, `waiting_for_event` and `skipped` (with the reason).
`status` is `no_snapshot`, `stale_snapshot` or `no_raw_table` when there was nothing to do.
