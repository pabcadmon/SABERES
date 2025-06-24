import pandas as pd

def clasificar_tipo(codigo, ssbb_df, ce_df, cev_df, do_df):
    if codigo in ssbb_df['Saber Básico'].astype(str).values:
        return 'SSBB'
    elif codigo in ce_df['CE'].astype(str).values:
        return 'CE'
    elif codigo in cev_df['Número'].astype(str).values:
        return 'CEv'
    elif codigo in do_df['Descriptor'].astype(str).values:
        return 'DO'
    return 'Otro'

def generar_tabla1(seleccionados, relaciones_long, ce_do_exp,
                   ssbb_df, ce_df, cev_df, do_df):
    resumen = []
    tipos = {
        "SSBB": "Saber Básico",
        "CE": "Competencia Específica",
        "CEv": "Criterio de Evaluación",
        "DO": "Descriptor Operativo"
    }
    por_tipo = {t: [] for t in tipos}

    for cod in seleccionados:
        tipo = clasificar_tipo(cod, ssbb_df, ce_df, cev_df, do_df)
        por_tipo[tipo].append(cod)

    for tipo, codigos in por_tipo.items():
        if not codigos:
            continue

        nombre_tipo = tipos[tipo]
        elementos = ', '.join(sorted(set(codigos)))

        # Inicializar relaciones
        sbs_rel = []
        ce_rel = []
        cev_rel = []
        do_rel = []

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
            'SSBB relacionados': ', '.join(sorted(set(sbs_rel))),
            'CE relacionados': ', '.join(sorted(set(ce_rel))),
            'CEv relacionados': ', '.join(sorted(set(cev_rel))),
            'DO relacionados': ', '.join(sorted(set(do_rel))),
        })

    return pd.DataFrame(resumen)




def generar_tabla2(seleccionados, relaciones_long, ce_do_exp):
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

        # Añadir CE relacionados a lista para mostrar en tabla
        seleccionados_completos = list(seleccionados)

    registros = []
    for sb in sbs_finales:
        relacionados = relaciones_long[relaciones_long['SB'].astype(str) == sb]
        fila = {'SB': sb}

        ce_vals = relacionados[relacionados['Tipo'].str.strip().str.upper() == 'CE']['Codigo'].dropna().astype(str).unique().tolist()
        cev_vals = relacionados[relacionados['Tipo'].str.strip().str.upper() == 'CEV']['Codigo'].dropna().astype(str).unique().tolist()

        fila['CE'] = ', '.join(sorted(ce_vals)) if ce_vals else ''
        fila['CEv'] = ', '.join(sorted(cev_vals)) if cev_vals else ''

        dos = ce_do_exp[ce_do_exp['CE'].astype(str).isin(ce_vals)]['DOs asociados'].dropna().astype(str).unique().tolist()
        fila['DO'] = ', '.join(sorted(dos)) if dos else ''

        registros.append(fila)

    return pd.DataFrame(registros)



def generar_tabla3(seleccionados, relaciones_long, ce_do_exp, descripciones,
                   ssbb_df, ce_df, cev_df, do_df):
    relacionados = set(seleccionados)

    dos = ce_do_exp[ce_do_exp['DOs asociados'].isin(seleccionados)]['CE'].unique()
    relacionados.update(dos)

    sb_rel = relaciones_long[
        relaciones_long['Codigo'].isin(relacionados) | relaciones_long['SB'].isin(relacionados)
    ]['SB'].dropna().unique()
    relacionados.update(sb_rel)

    ce_cev = relaciones_long[relaciones_long['SB'].isin(sb_rel)]
    relacionados.update(ce_cev['Codigo'].dropna())

    ces = ce_cev[ce_cev['Tipo'] == 'CE']['Codigo'].unique()
    dos = ce_do_exp[ce_do_exp['CE'].isin(ces)]['DOs asociados'].dropna().unique()
    relacionados.update(dos)

    df = pd.DataFrame({'Elemento': list(relacionados)})
    df['Tipo'] = df['Elemento'].apply(lambda x: clasificar_tipo(x, ssbb_df, ce_df, cev_df, do_df))
    df['Descripción'] = df['Elemento'].apply(lambda x: descripciones.get(str(x), 'Descripción no encontrada'))
    orden = {"SSBB": 0, "CE": 1, "CEv": 2, "DO": 3}
    df['Orden'] = df['Tipo'].map(orden)
    df = df.sort_values(['Orden', 'Elemento']).drop(columns='Orden')
    return df
