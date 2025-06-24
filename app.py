import streamlit as st
from core.ui import ejecutar_app
from core.config_loader import cargar_configuracion

def main():
    st.set_page_config(page_title="Relaciones curriculares", layout="wide")

    config_df = cargar_configuracion()

    # Crear etiquetas compuestas
    config_df["Etiqueta"] = config_df["Icono"] + " " + config_df["Asignatura"] + " (" + config_df["Curso"] + ")"

    seleccion_etiqueta = st.sidebar.selectbox("Selecciona materia y curso", config_df["Etiqueta"].tolist())

    fila = config_df[config_df["Etiqueta"] == seleccion_etiqueta].iloc[0]

    archivo = f"data/{fila['Archivo']}"
    asignatura = fila["Asignatura"]
    curso = fila["Curso"]
    icono = fila["Icono"]

    ejecutar_app(archivo, asignatura, curso, icono)

if __name__ == "__main__":
    main()
