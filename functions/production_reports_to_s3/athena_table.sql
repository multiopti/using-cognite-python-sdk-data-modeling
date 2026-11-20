-- Athena table over the files written by production_reports_to_s3 (run in workgroup polar-grafana).
-- Partition projection: Athena finds shift_date=YYYY-MM-DD / shift=day|night folders by itself, no MSCK REPAIR needed.
-- hour_start_utc is the time column for Grafana ($__timeFilter); hour_start_local is plant time (UTC-4) for downloads.
CREATE EXTERNAL TABLE IF NOT EXISTS polar_production.production_hourly (
  hour_start_utc              timestamp,
  hour_start_local            timestamp,
  hour_label                  string,
  slot                        int,
  line                        string,
  machine_type                string,
  machine                     string,
  production                  double,
  short_cans                  double,
  trimmer_jams                double,
  cans_by_short_can           double,
  cans_by_trimmer_jam         double,
  downtime_by_short_can_min   double,
  downtime_by_trimmer_jam_min double,
  downtime_min                double,
  scrap_kg                    double,
  scrap_pct                   double,
  efficiency_pct              double,
  retrac                      double,
  blow_off                    double,
  golpes_bobina               double,
  golpes_turno                double,
  observations                string,
  incident_code               int,
  incident_source             string,
  event_external_id           string,
  event_last_updated_utc      timestamp
)
PARTITIONED BY (shift_date string, shift string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://ingedaca-polar-production-data/production_hourly/'
TBLPROPERTIES (
  'projection.enabled'             = 'true',
  'projection.shift_date.type'     = 'date',
  'projection.shift_date.format'   = 'yyyy-MM-dd',
  'projection.shift_date.range'    = '2025-01-01,NOW',
  'projection.shift_date.interval' = '1',
  'projection.shift_date.interval.unit' = 'DAYS',
  'projection.shift.type'          = 'enum',
  'projection.shift.values'        = 'day,night',
  'storage.location.template'      = 's3://ingedaca-polar-production-data/production_hourly/shift_date=${shift_date}/shift=${shift}/'
)
