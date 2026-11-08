"""Local replacement of linea1_plant_view/cdf_service.py and linea3_plant_view/cdf_service.py for the plant server.

Same functions, same return shapes, but the numbers come from the plant's Node-RED (see planta_local/nodered_data.py)
instead of CDF. run_app.py puts this folder ahead of the app's own folder on sys.path when PLANT_DATA_SOURCE=nodered,
so the app's main.py runs unchanged.
"""
import nodered_data as nd
from config import ELEMENTS, MINSTER_TARGET          # the running app's own config (linea1 or linea3)


async def load_line1_values() -> dict:
    """{target: shift-to-date value} for config.ELEMENTS targets plus MINSTER_TARGET (e.g. LINE1_PRINTER_PRODUCTION_SHIFT).
    A target with no data is left out, as with the CDF version (main.py shows "--")."""
    return nd.line_values([el["target"] for el in ELEMENTS] + [MINSTER_TARGET])


async def load_machine_values(codes: list) -> dict:
    """{machine_code: {"production": float, "scrap": float}} for the shift running now."""
    return nd.machine_shift_totals(codes)
