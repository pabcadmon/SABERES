from core.loader import cargar_datos
from core.engine.generate import generate_from_excel

def test_generate_from_excel_genera_excel_bytes():
    data = cargar_datos("data/1ESO_GeH.xlsx")

    # coge 1 código real del propio dataset (evitas hardcodear “CE1”)
    ejemplo = str(data.ce_df["CE"].dropna().iloc[0])

    res = generate_from_excel("data/1ESO_GeH.xlsx", [ejemplo])

    assert hasattr(res, "excel_bytes")
    assert len(res.excel_bytes) > 1000

    # columnas esperadas en tablas
    assert "Tipo" in res.tabla1.columns
    assert "SB" in res.tabla2.columns
    assert "Elemento" in res.tabla3.columns
