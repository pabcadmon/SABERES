import pandas as pd

def cargar_datos(ruta):
    ssbb_df = pd.read_excel(ruta, sheet_name='SSBB')
    relaciones_df = pd.read_excel(ruta, sheet_name='SSBB-CE-CEv')
    cev_df = pd.read_excel(ruta, sheet_name='CEv')
    ce_df = pd.read_excel(ruta, sheet_name='CE')
    do_df = pd.read_excel(ruta, sheet_name='DO')
    ce_do_df = pd.read_excel(ruta, sheet_name='CE-DO')

    # Normalización general
    def limpiar_codigos(col):
        return col.astype(str).str.strip().str.rstrip('.')

    ssbb_df['Saber Básico'] = limpiar_codigos(ssbb_df['Saber Básico'])
    ce_df['CE'] = limpiar_codigos(ce_df['CE'])
    cev_df['Número'] = limpiar_codigos(cev_df['Número'])
    do_df['Descriptor'] = do_df['Descriptor'].astype(str).str.strip().str.rstrip('.')

    relaciones_df['CE'] = relaciones_df['CE'].astype(str).str.strip()
    relaciones_df['CEv'] = relaciones_df['CEv'].astype(str).str.strip()
    relaciones_df['SB'] = limpiar_codigos(relaciones_df['SB'])

    # Relaciones en formato largo
    relaciones_long = relaciones_df.melt(id_vars=['SB'], value_vars=['CE', 'CEv'],
                                         var_name='Tipo', value_name='Codigo')
    relaciones_long['Codigo'] = relaciones_long['Codigo'].str.split(',\s*')
    relaciones_long = relaciones_long.explode('Codigo')
    relaciones_long['Codigo'] = relaciones_long['Codigo'].str.strip().str.rstrip('.')
    relaciones_long.dropna(subset=['Codigo'], inplace=True)

    # Expandir CE-DO
    ce_do_df['DOs asociados'] = ce_do_df['DOs asociados'].astype(str).str.split(',\s*')
    ce_do_exp = ce_do_df.explode('DOs asociados')
    ce_do_exp['CE'] = limpiar_codigos(ce_do_exp['CE'])
    ce_do_exp['DOs asociados'] = limpiar_codigos(ce_do_exp['DOs asociados'])

    # Diccionario de descripciones
    descripciones = {}
    descripciones.update(ssbb_df.set_index('Saber Básico')['Descripción Completa'].to_dict())
    descripciones.update(cev_df.set_index('Número')['Descripción'].to_dict())
    descripciones.update(ce_df.set_index('CE')['Descripción del CE'].to_dict())
    descripciones.update(do_df.set_index('Descriptor')['Descripción'].to_dict())

    return ssbb_df, relaciones_long, ce_df, cev_df, do_df, ce_do_exp, descripciones
