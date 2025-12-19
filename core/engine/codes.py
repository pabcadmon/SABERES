import pandas as pd
from core.engine.sort import natural_sort_key

def build_codigos_df(ssbb_df: pd.DataFrame, ce_df: pd.DataFrame, cev_df: pd.DataFrame, do_df: pd.DataFrame) -> pd.DataFrame:
    ssbb = set(ssbb_df["Saber Básico"].astype(str).values)
    ce = set(ce_df["CE"].astype(str).values)
    cev = set(cev_df["Número"].astype(str).values)
    do = set(do_df["Descriptor"].astype(str).values)

    codigos = ssbb | ce | cev | do

    def _tipo(codigo: str) -> str:
        if codigo in ssbb: return "SSBB"
        if codigo in ce: return "CE"
        if codigo in cev: return "CEv"
        if codigo in do: return "DO"
        return "Otro"

    orden_tipo = {"SSBB": 0, "CE": 1, "CEv": 2, "DO": 3, "Otro": 99}

    rows = [(c, _tipo(c)) for c in codigos]
    df = pd.DataFrame(rows, columns=["Código", "Tipo"])

    # Orden por tipo + orden natural por código
    df["TipoOrden"] = df["Tipo"].map(orden_tipo).fillna(99)
    df = df.sort_values(
        by=["TipoOrden", "Código"],
        key=lambda s: s.map(natural_sort_key) if s.name == "Código" else s
    ).drop(columns="TipoOrden")

    # ✅ SIEMPRE crear Etiqueta al final
    df["Etiqueta"] = df["Tipo"].astype(str) + " | " + df["Código"].astype(str)

    return df
