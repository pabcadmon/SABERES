import streamlit as st
from core.loader import cargar_datos
from core.relaciones import generar_tabla1, generar_tabla2, generar_tabla3
from utils.export import exportar_excel
import pandas as pd

def ejecutar_app(ruta_excel, nombre_materia, curso, icono):
    ssbb_df, relaciones_long, ce_df, cev_df, do_df, ce_do_exp, descripciones = cargar_datos(ruta_excel)

    st.markdown(f"""
    <div style='text-align: left'>
        <h1>Relaciones curriculares</h1>
        <div style='font-size: 28px; font-weight: bold'>{icono} {nombre_materia}</div>
        <div style='font-size: 20px; font-weight: normal'>{curso}</div>
    </div>
    """, unsafe_allow_html=True)

    codigos = sorted(set(
        list(ssbb_df['Saber Básico'].astype(str)) +
        list(ce_df['CE'].astype(str)) +
        list(cev_df['Número'].astype(str)) +
        list(do_df['Descriptor'].astype(str))
    ))

    orden_tipo = {"SSBB": 0, "CE": 1, "CEv": 2, "DO": 3}
    codigos_con_tipo = [(codigo, 
                         "SSBB" if codigo in ssbb_df['Saber Básico'].astype(str).values else
                         "CE" if codigo in ce_df['CE'].astype(str).values else
                         "CEv" if codigo in cev_df['Número'].astype(str).values else
                         "DO" if codigo in do_df['Descriptor'].astype(str).values else "Otro")
                        for codigo in codigos]

    codigos_df = pd.DataFrame(codigos_con_tipo, columns=["Código", "Tipo"])
    codigos_df["TipoOrden"] = codigos_df["Tipo"].map(orden_tipo)
    codigos_df = codigos_df.sort_values(by=["TipoOrden", "Código"]).drop(columns="TipoOrden")
    codigos_df["Etiqueta"] = codigos_df["Tipo"] + " | " + codigos_df["Código"]

    st.write("### Filtrar por tipo:")

    st.markdown("""
    <style>
    .checkbox-row {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .checkbox-row > div {
        margin: 0 !important;
    }
    </style>
    <div class="checkbox-row">
    """, unsafe_allow_html=True)

    mostrar_ssbb = st.checkbox("Saberes Básicos (SB)", value=True, key="cb_sb")
    mostrar_ce = st.checkbox("Competencias Específicas (CE)", value=True, key="cb_ce")
    mostrar_cev = st.checkbox("Criterios de Evaluación (CEv)", value=True, key="cb_cev")
    mostrar_do = st.checkbox("Descriptores Operativos (DO)", value=True, key="cb_do")

    st.markdown("</div>", unsafe_allow_html=True)

    tipos_filtrados = []
    if mostrar_ssbb: tipos_filtrados.append("SSBB")
    if mostrar_ce: tipos_filtrados.append("CE")
    if mostrar_cev: tipos_filtrados.append("CEv")
    if mostrar_do: tipos_filtrados.append("DO")

    codigos_filtrados = codigos_df[codigos_df["Tipo"].isin(tipos_filtrados)]
    seleccionados_etiqueta = st.multiselect(
        "Selecciona los códigos:",
        options=codigos_filtrados["Etiqueta"].tolist()
    )
    seleccionados = [et.split(" | ")[1] for et in seleccionados_etiqueta]

    if seleccionados:
        try:
            # tabla1: resumen por tipo (antes tabla3)
            tabla1 = generar_tabla1(seleccionados, relaciones_long, ce_do_exp,
                                    ssbb_df, ce_df, cev_df, do_df)

            # tabla2: relaciones SB vs CE/CEv/DO (antes tabla1)
            tabla2 = generar_tabla2(seleccionados, relaciones_long, ce_do_exp)

            # tabla3: descripciones (antes tabla2)
            tabla3 = generar_tabla3(seleccionados, relaciones_long, ce_do_exp, 
                                    descripciones, ssbb_df, ce_df, cev_df, do_df)

            # Visual: marcar selección solo en tabla2 y tabla3
            def marcar_input(texto):
                if not isinstance(texto, str): return texto
                partes = [p.strip() for p in texto.split(',')]
                return ', '.join([f"»{p}«" if p in seleccionados else p for p in partes])

            tabla2_display = tabla2.copy()
            for col in tabla2_display.columns:
                if col != "SB":
                    tabla2_display[col] = tabla2_display[col].apply(marcar_input)

            tabla3_display = tabla3.copy()
            tabla3_display['Elemento'] = tabla3_display['Elemento'].apply(
                lambda x: f"»{x}«" if x in seleccionados else x)

            # Mostrar tablas
            st.subheader("Relaciones por tipo")  # antes: Tabla resumen por tipo
            st.dataframe(tabla1, use_container_width=True)

            st.subheader("Saberes Básicos relacionados")  # antes: Tabla básica de relaciones
            st.dataframe(tabla2_display, use_container_width=True)

            st.subheader("Descripciones de elementos mostrados")  # antes: Tabla detallada de descripciones
            st.dataframe(tabla3_display, use_container_width=True)

            # Exportar
            excel_data = exportar_excel(tabla1, tabla2, seleccionados, tabla3)
            st.download_button("Descargar Excel", data=excel_data,
                            file_name="relaciones_curriculares.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.error(f"Ocurrió un error generando las tablas: {e}")
