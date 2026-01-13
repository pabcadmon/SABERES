from core.loader import cargar_datos
from core.engine.types import CurriculumData

def test_cargar_datos_devuelve_secuenciaciondata():
    data = cargar_datos("data/1ESO_GeH.xlsx")  # pon un excel real que tengas en repo
    assert isinstance(data, CurriculumData)

    # columnas mínimas
    assert "Saber Básico" in data.ssbb_df.columns
    assert "CE" in data.ce_df.columns
    assert "Número" in data.cev_df.columns
    assert "Descriptor" in data.do_df.columns

    # relaciones_long mínimas
    assert set(["SB", "Tipo", "Codigo"]).issubset(set(data.relaciones_long.columns))

    # sets creados
    assert hasattr(data, "ce_set")
    assert hasattr(data, "ssbb_set")
