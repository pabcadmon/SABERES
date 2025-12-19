import pandas as pd
from core.engine.types import CurriculumData

def cargar_datos(ruta: str) -> CurriculumData:
    ssbb_df = pd.read_excel(ruta, sheet_name="SSBB")
    relaciones_df = pd.read_excel(ruta, sheet_name="SSBB-CE-CEv")
    cev_df = pd.read_excel(ruta, sheet_name="CEv")
    ce_df = pd.read_excel(ruta, sheet_name="CE")
    do_df = pd.read_excel(ruta, sheet_name="DO")
    ce_do_df = pd.read_excel(ruta, sheet_name="CE-DO")

    # Normalización general
    def limpiar_codigos(col: pd.Series) -> pd.Series:
        return col.astype(str).str.strip().str.rstrip(".")

    ssbb_df["Saber Básico"] = limpiar_codigos(ssbb_df["Saber Básico"])
    ce_df["CE"] = limpiar_codigos(ce_df["CE"])
    cev_df["Número"] = limpiar_codigos(cev_df["Número"])
    do_df["Descriptor"] = do_df["Descriptor"].astype(str).str.strip().str.rstrip(".")

    relaciones_df["CE"] = relaciones_df["CE"].astype(str).str.strip()
    relaciones_df["CEv"] = relaciones_df["CEv"].astype(str).str.strip()
    relaciones_df["SB"] = limpiar_codigos(relaciones_df["SB"])

    # Relaciones en formato largo
    relaciones_long = relaciones_df.melt(
        id_vars=["SB"], value_vars=["CE", "CEv"], var_name="Tipo", value_name="Codigo"
    )
    relaciones_long["Codigo"] = relaciones_long["Codigo"].astype(str).str.split(",")
    relaciones_long = relaciones_long.explode("Codigo")
    relaciones_long["Codigo"] = relaciones_long["Codigo"].astype(str).str.strip().str.rstrip(".")
    relaciones_long.dropna(subset=["Codigo"], inplace=True)

    # Expandir CE-DO
    ce_do_df["DOs asociados"] = ce_do_df["DOs asociados"].astype(str).str.split(",")
    ce_do_exp = ce_do_df.explode("DOs asociados")
    ce_do_exp["CE"] = limpiar_codigos(ce_do_exp["CE"])
    ce_do_exp["DOs asociados"] = limpiar_codigos(ce_do_exp["DOs asociados"])

    # Diccionario de descripciones
    descripciones = {}
    descripciones.update(ssbb_df.set_index("Saber Básico")["Descripción Completa"].to_dict())
    descripciones.update(cev_df.set_index("Número")["Descripción"].to_dict())
    descripciones.update(ce_df.set_index("CE")["Descripción del CE"].to_dict())
    descripciones.update(do_df.set_index("Descriptor")["Descripción"].to_dict())

    # Sets para clasificar rápido
    ssbb_set = set(ssbb_df["Saber Básico"].astype(str).values)
    ce_set = set(ce_df["CE"].astype(str).values)
    cev_set = set(cev_df["Número"].astype(str).values)
    do_set = set(do_df["Descriptor"].astype(str).values)

    return CurriculumData(
        ssbb_df=ssbb_df,
        relaciones_long=relaciones_long,
        ce_df=ce_df,
        cev_df=cev_df,
        do_df=do_df,
        ce_do_exp=ce_do_exp,
        descripciones=descripciones,
        ssbb_set=ssbb_set,
        ce_set=ce_set,
        cev_set=cev_set,
        do_set=do_set,
    )
