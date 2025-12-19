import pandas as pd

from core.engine.types import CurriculumData
from core.engine.sort import natural_sort_key

def clasificar_tipo(codigo: str, data: CurriculumData) -> str:
    c = str(codigo)
    if c in data.ssbb_set: return "SSBB"
    if c in data.ce_set: return "CE"
    if c in data.cev_set: return "CEv"
    if c in data.do_set: return "DO"
    return "Otro"

def generar_tabla1(seleccionados, data: CurriculumData):
    resumen = []
    tipos = {
        "SSBB": "Saber Básico",
        "CE": "Competencia Específica",
        "CEv": "Criterio de Evaluación",
        "DO": "Descriptor Operativo"
    }
    por_tipo = {t: [] for t in tipos}

    for cod in seleccionados:
        tipo = clasificar_tipo(cod, data)
        if tipo in por_tipo:
            por_tipo[tipo].append(str(cod))

    for tipo, codigos in por_tipo.items():
        if not codigos:
            continue

        nombre_tipo = tipos[tipo]
        elementos = ', '.join(sorted(set(codigos), key=natural_sort_key))

        # Inicializar relaciones
        sbs_rel = []
        ce_rel = []
        cev_rel = []
        do_rel = []

        relaciones_long = data.relaciones_long
        cev_df = data.cev_df
        ce_do_exp = data.ce_do_exp
        ce_df = data.ce_df

        if tipo == 'CE':
            # SB directamente relacionados
            sbs_rel = relaciones_long[
                (relaciones_long['Tipo'].str.strip().str.upper() == 'CE') &
                (relaciones_long['Codigo'].astype(str).isin(codigos))
            ]['SB'].dropna().astype(str).unique().tolist()

            # CEv por prefijo
            cev_rel = cev_df[
                cev_df['Número'].astype(str).str.startswith(tuple(str(c) + '.' for c in codigos))
            ]['Número'].dropna().astype(str).unique().tolist()

            # DO por relación directa
            do_rel = ce_do_exp[
                ce_do_exp['CE'].astype(str).isin(codigos)
            ]['DOs asociados'].dropna().astype(str).unique().tolist()

            ce_rel = codigos  # ellos mismos

        elif tipo == 'SSBB':
            sbs_rel = codigos

            ce_rel = relaciones_long[
                (relaciones_long['SB'].isin(codigos)) &
                (relaciones_long['Tipo'].str.strip().str.upper() == 'CE')
            ]['Codigo'].dropna().astype(str).unique().tolist()

            cev_rel = relaciones_long[
                (relaciones_long['SB'].isin(codigos)) &
                (relaciones_long['Tipo'].str.strip().str.upper() == 'CEV')
            ]['Codigo'].dropna().astype(str).unique().tolist()

            do_rel = ce_do_exp[
                ce_do_exp['CE'].isin(ce_rel)
            ]['DOs asociados'].dropna().astype(str).unique().tolist()

        elif tipo == 'CEv':
            cev_rel = codigos

            # Encontrar SB asociados
            sbs_rel = relaciones_long[
                (relaciones_long['Tipo'].str.strip().str.upper() == 'CEV') &
                (relaciones_long['Codigo'].astype(str).isin(codigos))
            ]['SB'].dropna().astype(str).unique().tolist()

            # CE padres por prefijo
            posibles_ce = [c.split('.')[0] for c in codigos if '.' in c]
            ce_rel = [c for c in posibles_ce if c in ce_df['CE'].astype(str).values]

            # DO asociados a esos CE
            do_rel = ce_do_exp[
                ce_do_exp['CE'].isin(ce_rel)
            ]['DOs asociados'].dropna().astype(str).unique().tolist()

        elif tipo == 'DO':
            do_rel = codigos

        resumen.append({
            'Tipo': nombre_tipo,
            'Elementos seleccionados': elementos,
            'SSBB relacionados': ', '.join(sorted(set(sbs_rel), key=natural_sort_key)),
            'CE relacionados': ', '.join(sorted(set(ce_rel), key=natural_sort_key)),
            'CEv relacionados': ', '.join(sorted(set(cev_rel), key=natural_sort_key)),
            'DO relacionados': ', '.join(sorted(set(do_rel), key=natural_sort_key)),
        })

    return pd.DataFrame(resumen)




def generar_tabla2(seleccionados, data: CurriculumData) -> pd.DataFrame:
    relaciones_long = data.relaciones_long
    ce_do_exp = data.ce_do_exp
    # SB directamente seleccionados o relacionados con seleccionados
    sb_directos = [s for s in seleccionados if s in relaciones_long['SB'].astype(str).values]
    sb_relacionados = relaciones_long[
        relaciones_long['Codigo'].astype(str).isin(seleccionados)
    ]['SB'].dropna().astype(str).unique().tolist()
    sbs_finales = list(set(sb_directos + sb_relacionados))

    # Si hay DO seleccionados, buscamos CE relacionados
    do_seleccionados = [s for s in seleccionados if s in ce_do_exp['DOs asociados'].astype(str).values]
    if do_seleccionados:
        # CE relacionados a esos DO
        ces_relacionados = ce_do_exp[
            ce_do_exp['DOs asociados'].astype(str).isin(do_seleccionados)
        ]['CE'].dropna().astype(str).unique().tolist()

        # Añadir esos CE relacionados a la lista
        sbs_de_dos = relaciones_long[
            (relaciones_long['Tipo'].str.strip().str.upper() == 'CE') &
            (relaciones_long['Codigo'].astype(str).isin(ces_relacionados))
        ]['SB'].dropna().astype(str).unique().tolist()

        # Añadir SB relacionados a los CE relacionados por DO
        sbs_finales = list(set(sbs_finales + sbs_de_dos))

    registros = []
    for sb in sbs_finales:
        relacionados = relaciones_long[relaciones_long['SB'].astype(str) == sb]
        fila = {'SB': sb}

        ce_vals = relacionados[relacionados['Tipo'].str.strip().str.upper() == 'CE']['Codigo'].dropna().astype(str).unique().tolist()
        cev_vals = relacionados[relacionados['Tipo'].str.strip().str.upper() == 'CEV']['Codigo'].dropna().astype(str).unique().tolist()

        fila['CE'] = ', '.join(sorted(ce_vals, key=natural_sort_key)) if ce_vals else ''
        fila['CEv'] = ', '.join(sorted(cev_vals, key=natural_sort_key)) if cev_vals else ''

        dos = ce_do_exp[ce_do_exp['CE'].astype(str).isin(ce_vals)]['DOs asociados'].dropna().astype(str).unique().tolist()
        fila['DO'] = ', '.join(sorted(dos, key=natural_sort_key)) if dos else ''
        registros.append(fila)

    df = pd.DataFrame(registros)
    if not df.empty and "SB" in df.columns:
        df = df.sort_values("SB", key=lambda s: s.map(natural_sort_key))
    return df



def generar_tabla3(seleccionados, data: CurriculumData):
    seleccionados = [str(s) for s in seleccionados]

    relacionados = set(seleccionados)
    relaciones_long = data.relaciones_long
    ce_do_exp = data.ce_do_exp

    # Si hay DO seleccionados, añadir CE vinculados
    dos = ce_do_exp[ce_do_exp["DOs asociados"].astype(str).isin(seleccionados)]["CE"].dropna().astype(str).unique()
    relacionados.update(dos)

    # Añadir SB relacionados con cualquier elemento relacionado
    sb_rel = relaciones_long[
        relaciones_long["Codigo"].astype(str).isin(relacionados) |
        relaciones_long["SB"].astype(str).isin(relacionados)
    ]["SB"].dropna().astype(str).unique()
    relacionados.update(sb_rel)

    # Añadir CE / CEv asociados a esos SB
    ce_cev = relaciones_long[relaciones_long["SB"].astype(str).isin(sb_rel)]
    relacionados.update(ce_cev["Codigo"].dropna().astype(str).unique())

    # Añadir DO asociados a los CE encontrados
    ces = ce_cev[ce_cev["Tipo"].astype(str).str.strip().str.upper() == "CE"]["Codigo"].dropna().astype(str).unique()
    dos2 = ce_do_exp[ce_do_exp["CE"].astype(str).isin(ces)]["DOs asociados"].dropna().astype(str).unique()
    relacionados.update(dos2)

    df = pd.DataFrame({"Elemento": sorted(relacionados)})
    df["Tipo"] = df["Elemento"].apply(lambda x: clasificar_tipo(x, data))
    df["Descripción"] = df["Elemento"].apply(lambda x: data.descripciones.get(str(x), "Descripción no encontrada"))

    orden = {"SSBB": 0, "CE": 1, "CEv": 2, "DO": 3, "Otro": 99}
    df["Orden"] = df["Tipo"].map(orden).fillna(99)
    df = df.sort_values(
        ["Orden", "Elemento"],
        key=lambda s: s.map(natural_sort_key) if s.name == "Elemento" else s
    )

    return df
