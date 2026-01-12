import pandas as pd

from core.engine.types import CurriculumData
from core.engine.sort import natural_sort_key
import unicodedata
import re

def _norm_code(value: str) -> str:
    return str(value or "").strip().rstrip(".")

def _norm_col(name: str) -> str:
    base = unicodedata.normalize("NFKD", str(name or ""))
    ascii_name = base.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())

def _find_col(df: pd.DataFrame, candidates) -> str | None:
    for col in df.columns:
        key = _norm_col(col)
        for cand in candidates:
            if cand in key:
                return col
    return None

def clasificar_tipo(codigo: str, data: CurriculumData) -> str:
    c = _norm_code(codigo)
    ssbb_set = {_norm_code(x) for x in data.ssbb_set}
    ce_set = {_norm_code(x) for x in data.ce_set}
    cev_set = {_norm_code(x) for x in data.cev_set}
    do_set = {_norm_code(x) for x in data.do_set}
    if c in ssbb_set: return "SSBB"
    if c in ce_set: return "CE"
    if c in cev_set: return "CEv"
    if c in do_set: return "DO"
    return "Otro"


def generar_tabla1(seleccionados, data: CurriculumData):
    seleccionados = [str(c).strip().rstrip(".") for c in (seleccionados or []) if str(c).strip()]
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

            ce_rel = []  # No mostrar CE seleccionados en su propia columna

        elif tipo == 'SSBB':
            sbs_rel = []  # No mostrar SSBB seleccionados en su propia columna

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
            cev_rel = []  # No mostrar CEv seleccionados en su propia columna

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
            do_rel = []  # No mostrar DO seleccionados en su propia columna

            # CE asociados a DO
            ce_rel = ce_do_exp[
                ce_do_exp['DOs asociados'].astype(str).isin(codigos)
            ]['CE'].dropna().astype(str).unique().tolist()

            # SB asociados a esos CE
            sbs_rel = relaciones_long[
                (relaciones_long['Tipo'].str.strip().str.upper() == 'CE') &
                (relaciones_long['Codigo'].astype(str).isin(ce_rel))
            ]['SB'].dropna().astype(str).unique().tolist()

            # CEv relacionados por prefijo CE
            cev_col = _find_col(cev_df, ["numero", "n"])
            if cev_col:
                cev_rel = cev_df[
                    cev_df[cev_col].astype(str).str.startswith(tuple(str(c) + '.' for c in ce_rel))
                ][cev_col].dropna().astype(str).unique().tolist()

        resumen.append({
            'Tipo': nombre_tipo,
            'Elementos seleccionados': elementos,
            'SSBB relacionados': ', '.join(sorted(set(sbs_rel), key=natural_sort_key)) or '-',
            'CE relacionados': ', '.join(sorted(set(ce_rel), key=natural_sort_key)) or '-',
            'CEv relacionados': ', '.join(sorted(set(cev_rel), key=natural_sort_key)) or '-',
            'DO relacionados': ', '.join(sorted(set(do_rel), key=natural_sort_key)) or '-',
        })

    return pd.DataFrame(resumen)


def generar_tabla2_ssbb(seleccionados, data: CurriculumData) -> pd.DataFrame:
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


def generar_tabla2_ce(seleccionados, data: CurriculumData) -> pd.DataFrame:
    """
    Genera tabla de relaciones para cada CE seleccionado/relacionado.
    Similar a generar_tabla2 pero para CE en lugar de SSBB.
    """
    relaciones_long = data.relaciones_long
    ce_do_exp = data.ce_do_exp
    
    # CE directamente seleccionados o relacionados
    ce_directos = [s for s in seleccionados if s in relaciones_long['Codigo'].astype(str).values and 
                   relaciones_long[relaciones_long['Codigo'].astype(str) == s]['Tipo'].str.strip().str.upper().iloc[0] == 'CE']
    ce_relacionados = relaciones_long[
        relaciones_long['SB'].astype(str).isin(seleccionados)
    ]['Codigo'].dropna().astype(str).unique().tolist()
    ce_relacionados = [c for c in ce_relacionados if c in relaciones_long[relaciones_long['Tipo'].str.strip().str.upper() == 'CE']['Codigo'].values]
    
    ces_finales = list(set(ce_directos + ce_relacionados))

    registros = []
    for ce in ces_finales:
        relacionados = relaciones_long[relaciones_long['Codigo'].astype(str) == ce]
        fila = {'CE': ce}

        sb_vals = relacionados[relacionados['Codigo'].astype(str) == ce]['SB'].dropna().astype(str).unique().tolist()
        fila['SSBB'] = ', '.join(sorted(sb_vals, key=natural_sort_key)) if sb_vals else ''

        # CEv por prefijo del CE
        cev_vals = data.cev_df[
            data.cev_df['Número'].astype(str).str.startswith(str(ce) + '.')
        ]['Número'].dropna().astype(str).unique().tolist()
        fila['CEv'] = ', '.join(sorted(cev_vals, key=natural_sort_key)) if cev_vals else ''

        # DO por relación directa
        dos = ce_do_exp[ce_do_exp['CE'].astype(str) == ce]['DOs asociados'].dropna().astype(str).unique().tolist()
        fila['DO'] = ', '.join(sorted(dos, key=natural_sort_key)) if dos else ''
        
        registros.append(fila)

    df = pd.DataFrame(registros)
    if not df.empty and "CE" in df.columns:
        df = df.sort_values("CE", key=lambda s: s.map(natural_sort_key))
    return df


def generar_tabla2_cev(seleccionados, data: CurriculumData) -> pd.DataFrame:
    """
    Genera tabla de relaciones para cada CEv seleccionado/relacionado.
    """
    relaciones_long = data.relaciones_long
    ce_do_exp = data.ce_do_exp
    
    # CEv directamente seleccionados o relacionados
    cev_directos = [s for s in seleccionados if s in relaciones_long['Codigo'].astype(str).values and 
                    relaciones_long[relaciones_long['Codigo'].astype(str) == s]['Tipo'].str.strip().str.upper().iloc[0] == 'CEV']
    cev_relacionados = relaciones_long[
        relaciones_long['SB'].astype(str).isin(seleccionados)
    ]['Codigo'].dropna().astype(str).unique().tolist()
    cev_relacionados = [c for c in cev_relacionados if c in relaciones_long[relaciones_long['Tipo'].str.strip().str.upper() == 'CEV']['Codigo'].values]
    
    cevs_finales = list(set(cev_directos + cev_relacionados))

    registros = []
    for cev in cevs_finales:
        relacionados = relaciones_long[relaciones_long['Codigo'].astype(str) == cev]
        fila = {'CEv': cev}

        sb_vals = relacionados[relacionados['Codigo'].astype(str) == cev]['SB'].dropna().astype(str).unique().tolist()
        fila['SSBB'] = ', '.join(sorted(sb_vals, key=natural_sort_key)) if sb_vals else ''

        # CE padre por prefijo
        ce_padre = str(cev).split('.')[0] if '.' in str(cev) else ''
        fila['CE'] = ce_padre if ce_padre in data.ce_df['CE'].astype(str).values else ''

        # DO por relación con el CE
        dos = ce_do_exp[ce_do_exp['CE'].astype(str) == ce_padre]['DOs asociados'].dropna().astype(str).unique().tolist() if ce_padre else []
        fila['DO'] = ', '.join(sorted(dos, key=natural_sort_key)) if dos else ''
        
        registros.append(fila)

    df = pd.DataFrame(registros)
    if not df.empty and "CEv" in df.columns:
        df = df.sort_values("CEv", key=lambda s: s.map(natural_sort_key))
    return df


def generar_tabla2_do(seleccionados, data: CurriculumData) -> pd.DataFrame:
    """
    Genera tabla de relaciones para cada DO seleccionado/relacionado.
    """
    relaciones_long = data.relaciones_long
    ce_do_exp = data.ce_do_exp
    
    # DO directamente seleccionados o relacionados
    do_directos = [s for s in seleccionados if s in ce_do_exp['DOs asociados'].astype(str).values]
    
    # CE relacionados a seleccionados
    ce_relacionados = relaciones_long[
        relaciones_long['SB'].astype(str).isin(seleccionados) &
        (relaciones_long['Tipo'].str.strip().str.upper() == 'CE')
    ]['Codigo'].dropna().astype(str).unique().tolist()
    
    # DO relacionados a esos CE
    do_relacionados = ce_do_exp[
        ce_do_exp['CE'].astype(str).isin(ce_relacionados)
    ]['DOs asociados'].dropna().astype(str).unique().tolist()
    
    dos_finales = list(set(do_directos + do_relacionados))

    registros = []
    for do in dos_finales:
        fila = {'DO': do}

        # CE asociado
        ce_vals = ce_do_exp[ce_do_exp['DOs asociados'].astype(str) == do]['CE'].dropna().astype(str).unique().tolist()
        fila['CE'] = ', '.join(sorted(ce_vals, key=natural_sort_key)) if ce_vals else ''

        # CEv del CE
        cev_vals = []
        if ce_vals:
            for ce in ce_vals:
                cevs = data.cev_df[
                    data.cev_df['Número'].astype(str).str.startswith(str(ce) + '.')
                ]['Número'].dropna().astype(str).unique().tolist()
                cev_vals.extend(cevs)
        fila['CEv'] = ', '.join(sorted(set(cev_vals), key=natural_sort_key)) if cev_vals else ''

        # SSBB relacionados a los CE
        sb_vals = relaciones_long[
            (relaciones_long['Codigo'].astype(str).isin(ce_vals)) &
            (relaciones_long['Tipo'].str.strip().str.upper() == 'CE')
        ]['SB'].dropna().astype(str).unique().tolist()
        fila['SSBB'] = ', '.join(sorted(set(sb_vals), key=natural_sort_key)) if sb_vals else ''
        
        registros.append(fila)

    df = pd.DataFrame(registros)
    if not df.empty and "DO" in df.columns:
        df = df.sort_values("DO", key=lambda s: s.map(natural_sort_key))
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
