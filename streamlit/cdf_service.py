from datetime import timedelta
import pandas as pd
import streamlit as st
from cognite.client import AsyncCogniteClient
from cognite.client.data_classes import EventUpdate, EventWrite

from config import SHIFT_MAP

@st.cache_resource
def get_cognite_client():
    return AsyncCogniteClient()

client = get_cognite_client()

def get_meta_num(meta: dict, keys: list, default: float = 0.0) -> float:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        k_lower = k.lower()
        if k_lower in meta_lower and meta_lower[k_lower] is not None:
            try:
                val_str = str(meta_lower[k_lower]).replace('%', '').strip()
                return float(val_str)
            except (ValueError, TypeError):
                continue
    return default

def get_meta_str(meta: dict, keys: list, default: str = "") -> str:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        k_lower = k.lower()
        if k_lower in meta_lower and meta_lower[k_lower] is not None:
            return str(meta_lower[k_lower])
    return default

async def load_shift_report_from_cdf(machine_code: str, m_type: str, fecha_str: str, turno_label: str) -> pd.DataFrame:
    fecha_clean = fecha_str.replace("-", "")
    shift_code = SHIFT_MAP.get(turno_label, 'day')

    m_code_clean = machine_code.lower()
    alt_codes = [m_code_clean]
    
    if "minster" in m_code_clean or "min" in m_code_clean:
        if "1" in m_code_clean:
            alt_codes.extend(["minster_l1", "min11", "minster11"])
        elif "3" in m_code_clean:
            alt_codes.extend(["minster_l3", "min31", "minster31"])
    elif m_code_clean.startswith("std") or m_code_clean.startswith("standum"):
        alt_codes.extend([
            m_code_clean.replace("std", "standum"),
            m_code_clean.replace("standum", "std")
        ])
    elif m_code_clean.startswith("is") or m_code_clean.startswith("ispray"):
        alt_codes.extend([
            m_code_clean.replace("ispray", "is"),
            m_code_clean.replace("is", "ispray")
        ])

    candidate_prefixes = []
    for code in set(alt_codes):
        candidate_prefixes.extend([
            f"report_{code}_{fecha_clean}_{shift_code}",
            f"report_{code.upper()}_{fecha_clean}_{shift_code}",
            f"{code}_{fecha_clean}_{shift_code}"
        ])

    events = []
    for prefix in candidate_prefixes:
        res = await client.events.list(type="Production Report", external_id_prefix=prefix, limit=100)
        if res:
            events = list(res)
            break
        res_no_type = await client.events.list(external_id_prefix=prefix, limit=100)
        if res_no_type:
            events = list(res_no_type)
            break

    rows = []
    for evt in events:
        meta = getattr(evt, 'metadata', None) or {}
        ext_id = getattr(evt, 'external_id', '') or ''
        
        try:
            slot_num = int(ext_id.split("_entry_")[-1])
        except Exception:
            slot_num = int(meta.get('slot_index', meta.get('slot', 1)))

        if m_type == "PRINTER":
            rows.append({
                'Slot': slot_num,
                'Producción x hora': get_meta_num(meta, ['hourly_production', 'production', 'prod_hora', 'delta_prod']),
                'Retrac-x-hora': get_meta_num(meta, ['hourly_retrac', 'retrac', 'delta_retrac']),
                'Blow of': get_meta_num(meta, ['blow_off', 'blow_of', 'delta_blowoff']),
                'Tiempo de parada': get_meta_num(meta, ['downtime_minutes', 'tiempo_de_parada', 'downtime']),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', 'efficiency', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operación estándar')
            })
        elif m_type == "MINSTER":
            rows.append({
                'Slot': slot_num,
                'Golpes Bobina': get_meta_num(meta, ['golpes_bobina_hora', 'golpes_bobina', 'coil_strokes']),
                'Golpes Turno': get_meta_num(meta, ['golpes_turno_hora', 'golpes_turno', 'shift_strokes']),
                'Tiempo Parada (min)': get_meta_num(meta, ['downtime_minutes', 'tiempo_de_parada', 'downtime']),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', '% eficiencia', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operación estándar')
            })
        elif m_type == "ISPRAY":
            rows.append({
                'Slot': slot_num,
                'Producción x hora': get_meta_num(meta, ['hourly_production', 'production', 'prod_hora', 'delta_prod']),
                'Tiempo Parada (min)': get_meta_num(meta, ['downtime_minutes', 'tiempo_de_parada', 'downtime']),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', '% eficiencia', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operación estándar')
            })
        else:
            rows.append({
                'Slot': slot_num,
                'PROD. LATAS': get_meta_num(meta, ['hourly_production', 'prod. latas', 'prod_latas', 'production', 'delta_prod']),
                'LAT CORTAS': get_meta_num(meta, ['short_cans_per_hour', 'lat cortas', 'latas_cortas', 'delta_latas_cortas']),
                'TRANC TRIMMER': get_meta_num(meta, ['trimmer_jams_per_hour', 'tranc trimmer', 'trancamiento_trimmer', 'delta_tranc_trim']),
                'LAT x LAT CORTAS': get_meta_num(meta, ['cans_by_short_can', 'lat x lat cortas']),
                'LAT x TRANC TRIM': get_meta_num(meta, ['cans_by_trimmer_jam', 'lat x tranc trim']),
                'Tiempo prom de parada x lat cort (min)': get_meta_num(meta, ['downtime_by_short_can_min', 'tiempo prom de parada x lat cort (min)', 'prom de parada x lat cort (min)']),
                'Tiempo prom de parada x tranc trim (min)': get_meta_num(meta, ['downtime_by_trimmer_jam_min', 'tiempo prom de parada x tranc trim (min)', 'prom de parada x tranc trim (min)']),
                'Tiempo parada (min)': get_meta_num(meta, ['total_downtime_min', 'tiempo parada (min)', 'downtime_min']),
                'Merma (kg)': get_meta_num(meta, ['merma_kg', 'merma']),
                '% Merma': get_meta_str(meta, ['pct_merma', '% merma'], '0.00%'),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', '% eficiencia', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operación estándar')
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()

async def save_observations_to_cdf(
    machine_code: str, 
    fecha_str: str, 
    turno_label: str, 
    edited_df: pd.DataFrame, 
    filtered_df: pd.DataFrame
) -> int:
    fecha_clean = fecha_str.replace("-", "")
    shift_code = SHIFT_MAP.get(turno_label, 'day')
    m_code_clean = machine_code.lower()
    prefix = f"report_{m_code_clean}_{fecha_clean}_{shift_code}"

    existing_events = await client.events.list(
        type="Production Report", 
        external_id_prefix=prefix, 
        limit=100
    )
    if not existing_events:
        existing_events = await client.events.list(
            external_id_prefix=prefix, 
            limit=100
        )

    event_map = {}
    for evt in existing_events:
        ext_id = getattr(evt, 'external_id', '') or (evt.get('external_id', '') if isinstance(evt, dict) else '')
        meta = getattr(evt, 'metadata', {}) or (evt.get('metadata', {}) if isinstance(evt, dict) else {})
        try:
            slot_num = int(ext_id.split("_entry_")[-1])
        except Exception:
            slot_num = int(meta.get('slot_index', meta.get('slot', 1)))
        event_map[slot_num] = evt

    events_to_create = []
    updates_to_send = []

    for idx, row in edited_df.iterrows():
        slot_num = int(filtered_df.loc[idx, 'Slot'])
        nueva_obs = str(row['Observaciones'])
        ext_id = f"{prefix}_entry_{slot_num}"

        if slot_num in event_map:
            existing_evt = event_map[slot_num]
            current_meta = getattr(existing_evt, 'metadata', None)
            if current_meta is None and isinstance(existing_evt, dict):
                current_meta = existing_evt.get('metadata', {})
            current_meta = dict(current_meta or {})
            
            if current_meta.get('observations') != nueva_obs or current_meta.get('observaciones') != nueva_obs:
                current_meta['observations'] = nueva_obs
                current_meta['observaciones'] = nueva_obs
                
                evt_id = getattr(existing_evt, 'id', None)
                if evt_id:
                    evt_update = EventUpdate(id=evt_id)
                else:
                    evt_update = EventUpdate(external_id=ext_id)
                
                evt_update.metadata.set(current_meta)
                updates_to_send.append(evt_update)
        else:
            new_meta = {
                "slot": str(slot_num),
                "slot_index": str(slot_num),
                "observations": nueva_obs,
                "observaciones": nueva_obs
            }
            for col in filtered_df.columns:
                if col not in ['Slot', 'Hora', 'Observaciones']:
                    new_meta[col.lower().replace(' ', '_')] = str(filtered_df.loc[idx, col])

            events_to_create.append(
                EventWrite(
                    external_id=ext_id,
                    type="Production Report",
                    description=f"Reporte {m_code_clean} - Slot {slot_num}",
                    metadata=new_meta
                )
            )

    if updates_to_send:
        await client.events.update(updates_to_send)
    if events_to_create:
        await client.events.create(events_to_create)

    return len(updates_to_send) + len(events_to_create)

async def fetch_heartbeat_status() -> str:
    try:
        res = await client.time_series.data.retrieve_latest(external_id="ActivoSimulacion.HEARTBEAT")
        if res is None:
            return "Sin datos"

        if isinstance(res, (list, tuple)) or type(res).__name__.endswith("List"):
            if not res:
                return "Sin datos"
            dp = res[0]
        else:
            dp = res

        if getattr(dp, "has_datapoint", True) is False:
            return "Sin datos"

        timestamp = getattr(dp, 'timestamp', None)
        value = getattr(dp, 'value', None)

        if timestamp is not None:
            if isinstance(timestamp, (int, float)):
                dt_gmt4 = pd.to_datetime(timestamp, unit='ms') - timedelta(hours=4)
            else:
                dt_gmt4 = pd.to_datetime(timestamp) - timedelta(hours=4)

            dt_str = dt_gmt4.strftime("%Y-%m-%d %H:%M:%S")
            return f"{dt_str} (GMT-4) | Valor: {value}"
        elif value is not None:
            return f"Valor: {value}"

    except Exception as e:
        return f"Error leyendo heartbeat ({e})"
    return "Sin datos"