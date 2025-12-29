# core/engine/generate.py
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

from core.loader import cargar_datos
from core.relaciones import generar_tabla1, generar_tabla2_ssbb, generar_tabla3, generar_tabla2_ce, generar_tabla2_cev, generar_tabla2_do
from utils.export import exportar_excel


@dataclass
class GenerateResult:
    tabla1: pd.DataFrame
    tabla2_ssbb: pd.DataFrame
    tabla2_ce: pd.DataFrame
    tabla2_cev: pd.DataFrame
    tabla2_do: pd.DataFrame
    tabla3: pd.DataFrame
    excel_bytes: Optional[bytes] = None


def generate_from_excel(
    ruta_excel: str,
    seleccionados: List[str],
    build_excel: bool = True,
) -> GenerateResult:
    data = cargar_datos(ruta_excel)

    tabla1 = generar_tabla1(seleccionados, data)
    tabla2_ssbb = generar_tabla2_ssbb(seleccionados, data)
    tabla2_ce = generar_tabla2_ce(seleccionados, data)
    tabla2_cev = generar_tabla2_cev(seleccionados, data)
    tabla2_do = generar_tabla2_do(seleccionados, data)
    tabla3 = generar_tabla3(seleccionados, data)

    excel_bytes: Optional[bytes] = None
    if build_excel:
        excel_io = exportar_excel(tabla1, tabla2_ssbb, tabla2_ce, tabla2_cev, tabla2_do, tabla3, seleccionados)
        # si ya devuelve bytes, esto no rompe
        excel_bytes = excel_io.getvalue() if hasattr(excel_io, "getvalue") else excel_io

    return GenerateResult(
        tabla1=tabla1,
        tabla2_ssbb=tabla2_ssbb,
        tabla2_ce=tabla2_ce,
        tabla2_cev=tabla2_cev,
        tabla2_do=tabla2_do,
        tabla3=tabla3,
        excel_bytes=excel_bytes,
    )
