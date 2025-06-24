import streamlit as st
import pandas as pd
from io import BytesIO

@st.cache_data
def cargar_datos():
    ssbb_df = pd.read_excel('SSBB.xlsx', sheet_name='SSBB')
    relaciones_df = pd.read_excel('SSBB.xlsx', sheet_name='SSBB-CE-CEv')
    cev_df = pd.read_excel('SSBB.xlsx', sheet_name='CEv')
    ce_df = pd.read_excel('SSBB.xlsx', sheet_name='CE')
    do_df = pd.read_excel('SSBB.xlsx', sheet_name='DO')
    ce_do_df = pd.read_excel('SSBB.xlsx', sheet_name='CE-DO')

    # Normalización de datos
    ssbb_df['Saber Básico'] = ssbb_df['Saber Básico'].str.strip()
    ce_df['CE'] = ce_df['CE'].astype(str).str.strip()
    cev_df['Número'] = cev_df['Número'].astype(str).str.strip()
    do_df['Descriptor'] = do_df['Descriptor'].str.strip()
    
    # Preparar relaciones SSBB-CE-CEv
    relaciones_df['CE'] = relaciones_df['CE'].astype(str).str.strip()
    relaciones_df['Cev'] = relaciones_df['Cev'].astype(str).str.strip()

    relaciones_long = relaciones_df.melt(id_vars=['SB'], value_vars=['CE', 'Cev'],
                                         var_name='Tipo', value_name='Codigo')
    relaciones_long['Codigo'] = relaciones_long['Codigo'].str.split(',\s*')
    relaciones_long = relaciones_long.explode('Codigo')
    relaciones_long['Codigo'] = relaciones_long['Codigo'].str.strip()
    relaciones_long.dropna(subset=['Codigo'], inplace=True)

    # Preparar CE-DO
    ce_do_df['DOs asociados'] = ce_do_df['DOs asociados'].astype(str).str.split(',\s*')
    ce_do_exp = ce_do_df.explode('DOs asociados')
    ce_do_exp['DOs asociados'] = ce_do_exp['DOs asociados'].str.strip()

    # Diccionario de descripciones
    descripciones = {}
    descripciones.update(ssbb_df.set_index('Saber Básico')['Descripción Completa'].to_dict())
    descripciones.update(cev_df.set_index('Número')['Descripción'].to_dict())
    descripciones.update(ce_df.set_index('CE')['Descripción del CE'].to_dict())
    descripciones.update(do_df.set_index('Descriptor')['Descripción'].to_dict())

    return ssbb_df, relaciones_long, ce_df, cev_df, do_df, ce_do_exp, descripciones

def obtener_relaciones(codigos, relaciones_long, ce_do_exp):
    # Crear el conjunto de códigos iniciales, asegurándonos de que todo esté en formato de texto
    relacionados = set(map(str, codigos))
    
    # Paso 1: Si son DO → buscar CE relacionados usando ce_do_exp
    dos = ce_do_exp[ce_do_exp['DOs asociados'].isin(codigos)]['CE'].unique()
    if dos.size > 0:
        # Convertir los CE encontrados en la búsqueda de DO a string y añadirlos
        relacionados.update(map(str, dos))
    
    # Paso 2: Buscar SB relacionados con los CE y DO encontrados hasta ahora
    sb_rel = relaciones_long[relaciones_long['Codigo'].isin(relacionados) | relaciones_long['SB'].isin(relacionados)]['SB'].unique()
    relacionados.update(map(str, sb_rel))
    
    # Paso 3: Buscar CE y CEv relacionados con los nuevos SB
    ce_cev = relaciones_long[relaciones_long['SB'].isin(sb_rel)]
    relacionados.update(map(str, ce_cev['Codigo'].unique()))  # Añadir los nuevos CE encontrados

    # Paso 4: Buscar DO asociados a los nuevos CE encontrados
    ces = ce_cev[ce_cev['Tipo'] == 'CE']['Codigo'].unique()
    dos = ce_do_exp[ce_do_exp['CE'].isin(map(int, ces))]['DOs asociados'].dropna().unique()
    relacionados.update(map(str, dos))  # Añadir los DO encontrados a partir de los nuevos CE
    
    return relacionados

def clasificar_tipo(e, ssbb_df, ce_df, cev_df, do_df):
    if e in ssbb_df['Saber Básico'].values:
        return "SSBB"
    elif e in ce_df['CE'].astype(str).values:
        return "CE"
    elif e in cev_df['Número'].astype(str).values:
        return "CEv"
    elif e in do_df['Descriptor'].values:
        return "DO"
    return "Otro"

def generar_tablas(codigos, relaciones_long, ce_do_exp, descripciones, ssbb_df, ce_df, cev_df, do_df):
    relacionados = obtener_relaciones(codigos, relaciones_long, ce_do_exp)

    # Tabla básica
    pivot = relaciones_long[relaciones_long['SB'].isin(relacionados)].pivot_table(
        index='SB', columns='Tipo', values='Codigo', aggfunc=lambda x: ', '.join(sorted(set(x)))
    ).reset_index()

    relaciones_ce = relaciones_long[relaciones_long['Tipo'] == 'CE'].copy()
    relaciones_ce['Codigo'] = relaciones_ce['Codigo'].astype(str)
    ce_do_exp['CE'] = ce_do_exp['CE'].astype(str)

    ce_dos = relaciones_ce.merge(ce_do_exp, left_on='Codigo', right_on='CE', how='left')
    ce_dos = ce_dos.groupby('SB')['DOs asociados'].apply(lambda x: ', '.join(sorted(set(x.dropna()))))
    ce_dos = ce_dos.reset_index()  # Mueve reset_index() aquí
    pivot = pivot.merge(ce_dos, on='SB', how='left')

    # Construir tabla detallada
    detallada = pd.DataFrame({'Elemento': list(relacionados)})
    detallada['Tipo'] = detallada['Elemento'].apply(lambda x: clasificar_tipo(x, ssbb_df, ce_df, cev_df, do_df))
    detallada['Descripción'] = detallada['Elemento'].apply(
        lambda x: descripciones.get(str(x), descripciones.get(x.strip(), 'Descripción no encontrada')))
    
    return pivot, detallada.sort_values(['Tipo', 'Elemento'])

def main():
    st.set_page_config(page_title="Relaciones curriculares", layout="wide")
    st.title("📘 Relaciones curriculares | 1º ESO Geografía e Historia")

    ssbb_df, relaciones_long, ce_df, cev_df, do_df, ce_do_exp, descripciones = cargar_datos()

    codigos = sorted(set(
        list(ssbb_df['Saber Básico'].astype(str)) +
        list(ce_df['CE'].astype(str)) +
        list(cev_df['Número'].astype(str)) +
        list(do_df['Descriptor'].astype(str))
    ))

    # Clasificar cada código y asociarlo a su tipo
    codigos_con_tipo = [(codigo, clasificar_tipo(codigo, ssbb_df, ce_df, cev_df, do_df)) for codigo in codigos]

    # Crear un DataFrame para mostrar en Streamlit
    codigos_df = pd.DataFrame(codigos_con_tipo, columns=["Código", "Tipo"])

    # Ordenar por tipo
    codigos_df = codigos_df.sort_values(by="Tipo")

    # Mostrar en la interfaz de usuario
    st.write("### Selecciona uno o varios códigos (SB, CE, CEv, DO):")
    seleccionados = st.multiselect(
        "Selecciona los códigos:",
        options=codigos_df['Código'].tolist(),
        format_func=lambda x: f"{x} ({codigos_df[codigos_df['Código'] == x]['Tipo'].values[0]})"  # Mostrar el tipo al lado
    )

    if seleccionados:
        try:
            tabla1, tabla2 = generar_tablas(seleccionados, relaciones_long, ce_do_exp, descripciones, 
                                           ssbb_df, ce_df, cev_df, do_df)

            st.subheader("📄 Tabla básica de relaciones")
            st.dataframe(tabla1, use_container_width=True)

            st.subheader("📜 Tabla detallada de descripciones")
            st.dataframe(tabla2, use_container_width=True)

            with BytesIO() as output:
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    tabla1.to_excel(writer, sheet_name='Relaciones', index=False)
                    tabla2.to_excel(writer, sheet_name='Descripciones', index=False)
                st.download_button("📥 Descargar Excel", data=output.getvalue(),
                                   file_name="relaciones_curriculares.xlsx", 
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.error(f"Ocurrió un error generando las tablas: {e}")

if __name__ == "__main__":
    main()