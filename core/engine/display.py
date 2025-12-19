# core/engine/display.py
import pandas as pd
from typing import List

def marcar_seleccion_tabla2(tabla2: pd.DataFrame, seleccionados: List[str]) -> pd.DataFrame:
    def marcar_input(texto):
        if not isinstance(texto, str):
            return texto
        partes = [p.strip() for p in texto.split(",")]
        return ", ".join([f"»{p}«" if p in seleccionados else p for p in partes])

    out = tabla2.copy()
    for col in out.columns:
        if col != "SB":
            out[col] = out[col].apply(marcar_input)
    return out

def marcar_seleccion_tabla3(tabla3: pd.DataFrame, seleccionados: List[str]) -> pd.DataFrame:
    out = tabla3.copy()
    out["Elemento"] = out["Elemento"].apply(lambda x: f"»{x}«" if x in seleccionados else x)
    return out
