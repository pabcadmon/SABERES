# app.py
import streamlit as st
import pandas as pd
from core.ui import ejecutar_app
from core.config_loader import cargar_configuracion

MATERIA_KEY = "__ssbb_materia_sel_id__"
QP_KEY = "sel"  # query param para materia

def _get_qparams():
    try:
        return dict(st.query_params)
    except Exception:
        return dict(st.experimental_get_query_params())

def _set_qparams(**kwargs):
    try:
        st.query_params.update(kwargs)
    except Exception:
        st.experimental_set_query_params(**kwargs)

def force_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        from streamlit.runtime.scriptrunner import RerunException, RerunData
        raise RerunException(RerunData(None))

# ----- Callbacks -----
def _on_change_materia():
    # Sincroniza con la URL para sobrevivir a resets de session_state
    sel_id = st.session_state.get(MATERIA_KEY, "")
    if sel_id:
        _set_qparams(**{QP_KEY: sel_id})
    st.session_state["acceso_ok"] = False
    st.session_state["clave_introducida"] = ""
    st.session_state["topbar_hidden"] = False
    st.session_state["access_attempted"] = False

def _try_access():
    clave_req = st.session_state.get("clave_actual_requerida", "")
    if clave_req:
        st.session_state["acceso_ok"] = (
            st.session_state.get("clave_introducida", "") == clave_req
        )
    else:
        st.session_state["acceso_ok"] = True
    st.session_state["access_attempted"] = True
    if st.session_state["acceso_ok"]:
        st.session_state["topbar_hidden"] = True

def main():
    st.set_page_config(page_title="Relaciones curriculares", layout="wide")

    # ===== Estado base =====
    st.session_state.setdefault("acceso_ok", False)
    st.session_state.setdefault("clave_introducida", "")
    st.session_state.setdefault("topbar_hidden", False)
    st.session_state.setdefault("access_attempted", False)

    # ===== Config =====
    config_df = cargar_configuracion()  # Asignatura, Curso, Archivo, Icono, (opcional) Clave
    if "Clave" not in config_df.columns:
        config_df["Clave"] = ""
    else:
        config_df["Clave"] = config_df["Clave"].fillna("")

    # ID estable
    config_df["ID"] = (
        config_df["Asignatura"].astype(str) + "|" +
        config_df["Curso"].astype(str) + "|" +
        config_df["Archivo"].astype(str)
    )
    config_df["Etiqueta"] = (
        config_df["Icono"].astype(str) + " " +
        config_df["Asignatura"].astype(str) + " (" +
        config_df["Curso"].astype(str) + ")"
    )
    config_df = config_df.sort_values(["Asignatura", "Curso"])

    ids = list(config_df["ID"])
    id_to_label = dict(zip(config_df["ID"], config_df["Etiqueta"]))
    id_to_row = {row["ID"]: row for _, row in config_df.iterrows()}

    # ===== Restaurar selección desde query param si session_state se limpió =====
    qparams = _get_qparams()
    qp_sel = qparams.get(QP_KEY)
    if isinstance(qp_sel, list):  # compat experimental_get_query_params
        qp_sel = qp_sel[0] if qp_sel else None
    valid_qp_sel = qp_sel in ids

    if MATERIA_KEY not in st.session_state:
        # 1) Si hay param ?sel válido en URL, úsalo
        if valid_qp_sel:
            st.session_state[MATERIA_KEY] = qp_sel
        else:
            # 2) Por defecto, primer ID y lo escribimos en la URL
            st.session_state[MATERIA_KEY] = ids[0]
            _set_qparams(**{QP_KEY: ids[0]})
    else:
        # Si ya hay selección en estado y la URL no coincide, sincroniza la URL
        cur = st.session_state[MATERIA_KEY]
        if cur and (qp_sel != cur):
            _set_qparams(**{QP_KEY: cur})

    # ===== Estilos =====
    st.markdown("""
    <style>
      .topbar {
        position: sticky; top: 0; z-index: 999;
        background: var(--background-color);
        padding: .5rem .75rem .75rem;
        border-bottom: 1px solid rgba(49,51,63,.2);
        backdrop-filter: blur(4px);
      }
      .floating-btn {
        position: fixed; right: 18px; bottom: 18px; z-index: 1000;
      }
      .floating-btn button { border-radius: 999px; }
    </style>
    """, unsafe_allow_html=True)

    # ===== TOPBAR (escondible) =====
    if not st.session_state["topbar_hidden"]:
        with st.container():
            st.markdown('<div class="topbar">', unsafe_allow_html=True)
            st.markdown("### 🔎 Selección de materia y acceso")
            c1, c2, c3 = st.columns([4, 3, 2])

            with c1:
                st.selectbox(
                    "Materia y curso",
                    options=ids,
                    index=ids.index(st.session_state[MATERIA_KEY]),
                    key=MATERIA_KEY,
                    format_func=lambda _id: id_to_label.get(_id, _id),
                    on_change=_on_change_materia
                )

            fila = id_to_row[st.session_state[MATERIA_KEY]]
            archivo = f"data/{fila['Archivo']}"
            asignatura = str(fila["Asignatura"])
            curso = str(fila["Curso"])
            icono = str(fila["Icono"])
            clave_requerida = str(fila.get("Clave", "")) or ""
            st.session_state["clave_actual_requerida"] = clave_requerida

            with c2:
                if clave_requerida:
                    st.text_input(
                        "🔐 Contraseña de acceso",
                        type="password",
                        key="clave_introducida",
                        on_change=_try_access
                    )
                else:
                    st.text_input("🔐 Contraseña (no requerida)", value="", disabled=True)

            with c3:
                st.write("")
                if st.button("Acceder", use_container_width=True):
                    _try_access()

            st.markdown("</div>", unsafe_allow_html=True)

    else:
        with st.container():
            st.markdown('<div class="floating-btn">', unsafe_allow_html=True)
            if st.button("Elegir otra asignatura"):
                st.session_state["topbar_hidden"] = False
                st.session_state["acceso_ok"] = False
                st.session_state["clave_introducida"] = ""
                st.session_state["access_attempted"] = False
                force_rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        fila = id_to_row[st.session_state[MATERIA_KEY]]
        archivo = f"data/{fila['Archivo']}"
        asignatura = str(fila["Asignatura"])
        curso = str(fila["Curso"])
        icono = str(fila["Icono"])
        clave_requerida = str(fila.get("Clave", "")) or ""
        st.session_state["clave_actual_requerida"] = clave_requerida

    # ===== Mensajes de acceso =====
    if st.session_state["access_attempted"]:
        if st.session_state["acceso_ok"]:
            st.success("Acceso concedido.")
        else:
            st.error("Contraseña incorrecta.")
        st.session_state["access_attempted"] = False

    # ===== Ejecutar / bloquear =====
    acceso_ok = st.session_state["acceso_ok"] if st.session_state.get("clave_actual_requerida", "") else True

    if acceso_ok:
        ejecutar_app(archivo, asignatura, curso, icono)
    else:
        st.info("Introduce la contraseña para continuar.")

if __name__ == "__main__":
    main()
