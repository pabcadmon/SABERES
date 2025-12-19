from core.loader import cargar_datos
from core.engine.normalize import normalize_codes

def test_normalize_ce_prefix():
    data = cargar_datos("data/1ESO_GeH.xlsx")
    out = normalize_codes(["CE1"], data)
    assert out[0] == "1"
