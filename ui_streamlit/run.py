# ui_streamlit/run.py
import streamlit as st
from core.loader import cargar_datos
from core.engine.codes import build_codigos_df
from core.engine.generate import generate_from_excel
from core.engine.display import marcar_seleccion_tabla2, marcar_seleccion_tabla3

def ejecutar_app_streamlit(ruta_excel, nombre_materia, curso, icono, selection_id: str):
    data = cargar_datos(ruta_excel)

    st.markdown(f"""
    <div style='text-align: left'>
        <h1>Relaciones curriculares</h1>
        <div style='font-size: 28px; font-weight: bold'>{icono} {nombre_materia}</div>
        <div style='font-size: 20px; font-weight: normal'>{curso}</div>
    </div>
    """, unsafe_allow_html=True)

    # === Construir códigos ===
    codigos_df = build_codigos_df(
        data.ssbb_df, data.ce_df, data.cev_df, data.do_df
    )

    # === Filtros por tipo ===
    st.write("### Filtrar por tipo:")

    mostrar_ssbb = st.checkbox("Saberes Básicos (SB)", value=True)
    mostrar_ce   = st.checkbox("Competencias Específicas (CE)", value=True)
    mostrar_cev  = st.checkbox("Criterios de Evaluación (CEv)", value=True)
    mostrar_do   = st.checkbox("Descriptores Operativos (DO)", value=True)

    tipos_filtrados = []
    if mostrar_ssbb: tipos_filtrados.append("SSBB")
    if mostrar_ce:   tipos_filtrados.append("CE")
    if mostrar_cev:  tipos_filtrados.append("CEv")
    if mostrar_do:   tipos_filtrados.append("DO")

    codigos_filtrados = codigos_df[codigos_df["Tipo"].isin(tipos_filtrados)]

    # === Multiselect ===
    ms_key = f"ms_codigos_{selection_id}"
    seleccionados_etiqueta = st.multiselect(
        "Selecciona los códigos:",
        options=codigos_filtrados["Etiqueta"].tolist(),
        key=ms_key
    )

    seleccionados = [et.split(" | ")[1] for et in seleccionados_etiqueta]

    if seleccionados:
        res = generate_from_excel(ruta_excel, seleccionados)

        tabla2_display = marcar_seleccion_tabla2(res.tabla2, seleccionados)
        tabla3_display = marcar_seleccion_tabla3(res.tabla3, seleccionados)

        st.subheader("Relaciones por tipo")
        st.dataframe(res.tabla1, width="stretch")

        st.subheader("Saberes Básicos relacionados")
        st.dataframe(tabla2_display, width="stretch")

        st.subheader("Descripciones de elementos mostrados")
        st.dataframe(tabla3_display, width="stretch")

        st.download_button(
            "Descargar Excel",
            data=res.excel_bytes,
            file_name="relaciones_curriculares.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
