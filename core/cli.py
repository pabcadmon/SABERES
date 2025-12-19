# core/cli.py
import argparse
from pathlib import Path

from core.engine.normalize import normalize_codes, NormalizationError
from core.engine.generate import generate_from_excel
from core.loader import cargar_datos

def main() -> int:
    parser = argparse.ArgumentParser(description="Generar relaciones curriculares a Excel.")
    parser.add_argument("--excel", required=True, help="Ruta al Excel curricular (input).")
    parser.add_argument("--out", default="exports/relaciones_curriculares.xlsx", help="Ruta del Excel de salida.")
    parser.add_argument("--codes", nargs="+", help="Códigos a incluir (SB/CE/CEv/DO). Si no se indican, usa el primer CE.")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = cargar_datos(str(excel_path))

    seleccionados = args.codes
    if not seleccionados:
        seleccionados = [str(data.ce_df["CE"].dropna().iloc[0])]
    else:
        try:
            seleccionados = normalize_codes(seleccionados, data)
        except NormalizationError as e:
            print("❌", str(e))
            print("Ejemplos de SSBB válidos:", sorted(list(data.ssbb_set))[:15])
            print("Ejemplos de CE válidos:", sorted(list(data.ce_set))[:15])
            print("Ejemplos de CEv válidos:", sorted(list(data.cev_set))[:15])
            print("Ejemplos de DO válidos:", sorted(list(data.do_set))[:15])
            return 2

        # Validación: comprobar que existen en los datos
        validos = data.ssbb_set | data.ce_set | data.cev_set | data.do_set
        invalidos = [c for c in seleccionados if c not in validos]

        if invalidos:
            print("❌ Códigos no encontrados:", invalidos)
            print("Ejemplos de SSBB válidos:", sorted(list(data.ssbb_set))[:15])
            print("Ejemplos de CE válidos:", sorted(list(data.ce_set))[:15])
            print("Ejemplos de CEv válidos:", sorted(list(data.cev_set))[:15])
            print("Ejemplos de DO válidos:", sorted(list(data.do_set))[:15])
            return 2

    res = generate_from_excel(str(excel_path), seleccionados)

    # res.excel_bytes es bytes (ya lo dejaste bien)
    out_path.write_bytes(res.excel_bytes)

    print(f"OK: {out_path}  (codes={seleccionados})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
