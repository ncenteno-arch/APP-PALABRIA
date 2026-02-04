# frontend/app.py
import streamlit as st
import requests
from fpdf import FPDF
import os
import time
import hashlib
from rapidfuzz.distance import Levenshtein as L
from streamlit.components.v1 import html as st_html
import altair as alt

st.set_page_config(page_title="PALABRIA", layout="centered")


PRETTY = {
    "total_frases": "Total de frases",
    "frases_con_tu_impersonal": "Posibles frases con 'tú' impersonal",
    "cambios_propuestos_modelo": "Cambios propuestos (modelo)",
    "cambios_realizados_usuario": "Cambios realizados (usuario)",
}
SHOW_KEYS = list(PRETTY.keys())


st.markdown("""
<style>
form[data-testid="stForm"] {
    margin-top: 5rem !important;  /* baja el bloque unos 5 cm */
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Reduce el espacio después de los gráficos Altair */
div[data-testid="stVegaLiteChart"] {
    margin-bottom: -0.5rem !important;   /* antes era ~2rem por defecto */
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    """
    <style>
    .spacer-1cm { height: 0.25rem; }
    .spacer-tabs { height: 1.1rem; }
    .block-container { padding-top: 2.0rem; padding-bottom: 1.5rem; }
    .h-section, .stMarkdown h2, .stMarkdown h3 {
      font-size: 1.25rem !important; font-weight: 700 !important;
      margin-top: .5rem !important; margin-bottom: 0 !important;
      line-height: 1.2; color: #111827;
    }
    [data-testid="stVerticalBlock"] > div { margin-bottom: 0.3rem; }

    .stTabs { margin-top: 0.35rem; }
    .stTabs [data-baseweb="tab"],
    .stTabs button[role="tab"] {
      font-size: 1.30rem !important; font-weight: 700 !important;
      padding: .50rem 1.00rem !important;
      border: 1px solid rgba(49,51,63,0.12) !important;
      border-radius: .55rem !important; background: #fff !important;
      margin-right: .5rem !important; line-height: 1.2 !important;
      min-height: 2.4rem !important;
    }
    .stTabs [data-baseweb="tab"] p,
    .stTabs button[role="tab"] p,
    .stTabs [data-baseweb="tab"] span,
    .stTabs button[role="tab"] span {
      font-size: 1.20rem !important; font-weight: 700 !important;
      line-height: 1.2 !important;
    }
    .stTabs [aria-selected="true"],
    .stTabs button[role="tab"][aria-selected="true"] {
      border-color: #2563eb !important;
      box-shadow: 0 0 0 2px rgba(37,99,235,0.08) inset !important;
    }

    /* --- Cajas de métricas --- */
    div[data-testid="stMetric"] {
      padding: 0.5rem 0.6rem !important;
      border: 1px solid rgba(49,51,63,0.15) !important;
      border-radius: 0.5rem !important;
      background: #ffffff !important;
      text-align: center !important;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }

    /* --- Título de cada métrica --- */
    div[data-testid="stMetricLabel"] {
      font-size: 1rem !important;
      font-weight: 500 !important;    
      color: #111827 !important;
      margin-bottom: 0.15rem !important;
      line-height: 1.15 !important;
      text-align: center !important;
    }

    /* --- Valor numérico --- */
    div[data-testid="stMetricValue"] {
      font-size: 1.15rem !important;
      font-weight: 600 !important;
      color: #000000 !important;
      text-align: center !important;
      line-height: 1.2 !important;
    }

    /* --- Cuadros de texto de lectura (original/modelo) --- */
    .readonly-box {
      border: 1px solid rgba(49,51,63,0.2);
      border-radius: 0.5rem;
      padding: 0.5rem 0.6rem;
      background: #ffffff;
      color: inherit;
      font-family: inherit;
      line-height: 1.45;
      width: 100%;
      box-sizing: border-box;
      max-width: 100%;
      overflow-x: hidden;
      overflow-y: auto;
      min-height: 150px;
      max-height: 300px;
    }
    .readonly-box[readonly] {
      background: #ffffff;
      color: inherit;
      cursor: default;
    }

    /* --- Títulos --- */
    section[data-testid="stVerticalBlock"] h1,
    section[data-testid="stVerticalBlock"] h2,
    section[data-testid="stVerticalBlock"] h3 {
        margin-bottom: 0.25rem !important;
    }

    div.stMarkdown h1, div.stMarkdown h2, div.stMarkdown h3 {
        margin-top: 0.2rem !important;
        margin-bottom: 0.15rem !important;
        line-height: 1.15 !important;
    }

    div[data-testid="stVerticalBlock"] > div + div {
        margin-top: -0.35rem !important;
    }

    section[data-testid="stVerticalBlock"] {
        margin-bottom: 0.3rem !important;
        padding-bottom: 0 !important;
    }

    section[data-testid="stVerticalBlock"] > div {
        margin-bottom: 0.15rem !important;
        padding-bottom: 0rem !important;
    }

    /* --- Formularios --- */
    div[data-testid="stRadio"],
    div[data-testid="stTextInput"],
    div[data-testid="stFileUploader"] {
        margin-top: -0.35rem !important;
        margin-bottom: -0.15rem !important;
    }

    /* --- Áreas de texto editables ("Pega aquí tu texto" y "Tu versión final") --- */
    div[data-testid="stTextArea"] {
        overflow: visible !important;
        margin-right: 0 !important;
        padding-right: 0 !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }

    div[data-testid="stTextArea"] > div {
        overflow: visible !important;
        width: 100% !important;
    }

    div[data-testid="stTextArea"] textarea {
        overflow-x: hidden !important;
        overflow-y: auto !important;
        width: 100% !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
        resize: vertical !important;     /* solo vertical */
        font-size: 1rem !important;
        line-height: 1.5 !important;
        border: 1px solid rgba(49,51,63,0.2) !important;
        border-radius: 0.5rem !important;
        padding: 0.5rem 0.6rem !important;
        background: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def save_text_as_pdf(text, filename="Texto_Corregido.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split("\n"):
        pdf.multi_cell(0, 10, line)
    pdf.output(filename)
    return filename

def fetch_status(backend_url, timeout=5):
    try:
        r = requests.get(f"{backend_url}/status/", timeout=timeout)
        if r.ok:
            data = r.json()
            return {
                "modelo_listo": bool(data.get("modelo_listo", False)),
                "progress": int(data.get("progress", 0)),
                "message": data.get("message", "⚡ Cargando…"),
            }
    except Exception as e:
        return {"modelo_listo": False, "progress": 0, "message": f"No conectado: {e}"}
    return {"modelo_listo": False, "progress": 0, "message": "Desconocido"}

def _normalize_for_diff(text: str) -> str:
    """
    Normalización mínima:
    - …  → ...
    - — / –  → -
    - “ ”  → "
    - ‘ ’  → '
    Mantiene saltos de línea.
    """

    if not text:
        return ""

    t = text
    t = t.replace("…", "...")
    t = (
        t.replace("“", '"')
         .replace("”", '"')
    )
    t = (
        t.replace("‘", "'")
         .replace("’", "'")
    )
    t = (
        t.replace("—", "-")
         .replace("–", "-")   
    )
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    return t.strip()


def word_levenshtein_count(a_text: str, b_text: str) -> int:
    a_tokens = _normalize_for_diff(a_text).split()
    b_tokens = _normalize_for_diff(b_text).split()
    return int(L.distance(a_tokens, b_tokens))

def pretty_int(x):
    try:
        fx = float(x)
        return int(fx) if fx.is_integer() else fx
    except Exception:
        return x

def pretty_hms(seconds: float) -> str:
    """⏱️ Formatea segundos a 'H h M min S s'."""
    try:
        s = int(round(float(seconds)))
    except Exception:
        s = 0
    h = s // 3600
    m = (s % 3600) // 60
    ss = s % 60
    parts = []
    if h > 0: parts.append(f"{h} h")
    if m > 0 or h > 0: parts.append(f"{m} min")
    parts.append(f"{ss} s")
    return " ".join(parts)

def inject_session_js(backend_url: str, username: str):
    js = f"""
    <script>
    (function(){{
      const backend = {repr(backend_url)};
      const username = {repr(username)};
      const hbUrl = backend + "/users/heartbeat";
      const loUrl = backend + "/users/logout";

      function postForm(url, dataObj) {{
        const formData = new URLSearchParams();
        for (const k in dataObj) formData.append(k, dataObj[k]);
        return fetch(url, {{
          method: "POST",
          mode: "cors",
          headers: {{"Content-Type":"application/x-www-form-urlencoded"}},
          body: formData.toString()
        }}).catch(()=>{{}});
      }}

      const sendHeartbeat = () => postForm(hbUrl, {{username}});
      // Heartbeat inicial y luego cada 20s
      sendHeartbeat();
      const hbTimer = setInterval(sendHeartbeat, 20000);

      function beaconLogout() {{
        try {{
          if (!navigator.sendBeacon) {{
            postForm(loUrl, {{username}});
            return;
          }}
          const data = new URLSearchParams();
          data.append("username", username);
          const blob = new Blob([data.toString()], {{type: "application/x-www-form-urlencoded"}});
          navigator.sendBeacon(loUrl, blob);
        }} catch (e) {{}}
      }}

      window.addEventListener("beforeunload", beaconLogout);
      document.addEventListener("visibilitychange", function(){{
        if (document.visibilityState === "hidden") beaconLogout();
      }});
    }})();
    </script>
    """
    st_html(js, height=0)

def has_current_analysis() -> bool:
    anal = st.session_state.get("last_analysis")
    if not anal:
        return False
    if anal.get("original_sentences") or anal.get("corrected_text"):
        return True
    return False

def clear_current_analysis():
    for k in ["last_input_digest","last_pdf_name","last_doc_id",
              "last_analysis","edited_text_area","__edited_for_doc"]:
        st.session_state.pop(k, None)

def _clear_status_cache():
    for k in ["modelo_listo","status_progress","status_message",
              "notificado_listo","last_status_check"]:
        st.session_state.pop(k, None)

def _clear_metrics_cache():
    for k in ["__cache_overview","__cache_documents"]:
        st.session_state.pop(k, None)
    for k in list(st.session_state.keys()):
        if str(k).startswith("__cache_doc_"):
            st.session_state.pop(k, None)

def _clear_input_cache():
    clear_current_analysis()

def _fetch_and_cache_doc_metrics(backend_url, doc_id: int):
    try:
        m = requests.get(f"{backend_url}/documents/{doc_id}/metrics", timeout=20).json()["metrics"]
        st.session_state[f"__cache_doc_{doc_id}"] = m
    except Exception:
        pass

def _post_user_changes(backend_url, doc_id: int, changes: int):
    try:
        requests.post(
            f"{backend_url}/documents/{doc_id}/user_changes",
            data={"changes": changes},
            timeout=10
        )
        st.session_state[f"__last_saved_changes_{doc_id}"] = int(changes)
        _fetch_and_cache_doc_metrics(backend_url, doc_id)
    except Exception:
        pass

def login():
    with st.form("login_form"):
        st.markdown("<h2 class='h-section'>🔓 Iniciar sesión</h2>", unsafe_allow_html=True)
        username = st.text_input("Nombre de usuario")
        submit = st.form_submit_button("Entrar")
        if submit:
            if username:
                backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                try:
                    r = requests.post(f"{backend_url}/users/login", data={"username": username}, timeout=10)
                    if r.ok and r.json().get("ok"):
                        st.session_state["usuario"] = username
                        st.session_state["logged_in"] = True
                        st.session_state["show_login"] = False
                        st.session_state["show_create_account"] = False
                        st.success(f"Bienvenido/a, {username}")
                        _clear_status_cache()
                        _clear_metrics_cache()
                        _clear_input_cache()
                        st.rerun()
                    else:
                        try:
                            msg = r.json().get("detail", r.text)
                        except Exception:
                            msg = r.text
                        st.error(msg or "No se pudo iniciar sesión.")
                except Exception as e:
                    st.error(f"Error conectando con backend: {e}")
            else:
                st.warning("Por favor, escribe un nombre de usuario.")

def create_account():
    with st.form("create_account_form"):
        st.markdown("<h2 class='h-section'>📝 Crear nueva cuenta</h2>", unsafe_allow_html=True)
        new_username = st.text_input("Elige un nombre de usuario (letras/números/_-. máx 32)")
        submit = st.form_submit_button("Crear cuenta")
        if submit:
            if new_username:
                backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                try:
                    r = requests.post(f"{backend_url}/users/create", data={"username": new_username}, timeout=10)
                    if r.ok and r.json().get("ok"):
                        st.session_state["usuario"] = new_username
                        st.session_state["logged_in"] = True
                        st.session_state["show_login"] = False
                        st.session_state["show_create_account"] = False
                        st.success(f"Cuenta creada para {new_username}")
                        _clear_status_cache()
                        _clear_metrics_cache()
                        _clear_input_cache()
                        st.rerun()
                    else:
                        try:
                            msg = r.json().get("detail", r.text)
                        except Exception:
                            msg = r.text
                        st.error(msg or "No se pudo crear la cuenta.")
                except Exception as e:
                    st.error(f"Error conectando con backend: {e}")
            else:
                st.warning("Por favor, escribe un nombre de usuario.")


def cargar_metricas(username, backend_url):
    ov = requests.get(f"{backend_url}/users/{username}/overview", timeout=20).json()
    docs = requests.get(f"{backend_url}/users/{username}/documents", timeout=20).json().get("documents", [])
    st.session_state["__cache_overview"] = ov
    st.session_state["__cache_documents"] = docs

def ver_mis_metricas(username, backend_url):
    st.markdown("<h2 class='h-section'>📊 Tus estadísticas globales</h2>", unsafe_allow_html=True)

    if "__cache_overview" not in st.session_state or "__cache_documents" not in st.session_state:
        try:
            cargar_metricas(username, backend_url)
            for d in st.session_state.get("__cache_documents", []):
                _fetch_and_cache_doc_metrics(backend_url, d["id"])
        except Exception as e:
            st.error(f"No se pudieron cargar las métricas: {e}")

    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button[kind="secondary"],
        div[data-testid="stButton"] > button#btn_refresh_metrics {
            background-color: #f0f0f0 !important;
            color: #333 !important;
            border: 1px solid #d1d5db !important;
            font-weight: 600 !important;
            transition: background-color 0.2s ease;
        }
        div[data-testid="stButton"] > button#btn_refresh_metrics:hover {
            background-color: #e5e5e5 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Actualizar métricas", key="btn_refresh_metrics", use_container_width=True):
        cargar_metricas(username, backend_url)
        for d in st.session_state.get("__cache_documents", []):
            _fetch_and_cache_doc_metrics(backend_url, d["id"])

    st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center !important;
    }
    div[data-testid="stMetricLabel"] {
        text-align: center !important;
        justify-content: center !important;
        align-items: center !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] {
        text-align: center !important;
        justify-content: center !important;
        align-items: center !important;
        font-weight: 500 !important;
        color: #000 !important;
        font-size: 0.97rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    ov = st.session_state.get("__cache_overview")
    docs = st.session_state.get("__cache_documents")

    if ov:
        usage = ov.get("usage", {})
        c1, c2 = st.columns(2, gap="medium")
        c1.metric("📄 Documentos procesados", ov.get("docs", 0))
        c2.metric("📆 Días en actividad", ov.get("login_days", 0))

        c3, c4 = st.columns(2, gap="medium")
        c3.metric("🔁 Inicios de sesión", usage.get("login", {}).get("count", 0))
        avg_secs = float(ov.get("avg_session_seconds", 0.0) or 0.0)
        c4.metric("⏱️ Tiempo medio por sesión", pretty_hms(avg_secs))

        c5, c6 = st.columns(2, gap="medium")
        c5.metric("📈 % docs con 'tú' impersonal", f"{float(ov.get('docs_with_tu_percent', 0.0) or 0.0):.1f}%")
        c6.metric("🛠️ % docs sin cambios", f"{float(ov.get('docs_no_changes_percent', 0.0) or 0.0):.1f}%")

        st.markdown("<h2 class='h-section'>📊 Promedios por métrica (histórico)</h2>", unsafe_allow_html=True)
        avg_metrics = ov.get("avg_metrics", {})
        if avg_metrics:
            st.markdown("""
            <style>
            .metric-row {
                padding: 0.4rem 0.8rem;
                border-radius: 0.4rem;
                margin-bottom: 0.25rem;
            }
            .metric-row:nth-child(odd) {
                background-color: #f9fafb;
            }
            .metric-row:nth-child(even) {
                background-color: #ffffff;
            }
            .metric-label {
                font-weight: 400;
                color: #374151;
            }
            .metric-value {
                float: right;
                font-weight: 500;
                color: #000000;
            }
            </style>
            """, unsafe_allow_html=True)

            html_rows = ""
            for key in SHOW_KEYS:
                if key in avg_metrics:
                    label = PRETTY.get(key, key)
                    value = pretty_int(round(avg_metrics[key], 2))
                    html_rows += f"<div class='metric-row'><span class='metric-label'>{label}</span><span class='metric-value'>{value}</span></div>"

            st.markdown(html_rows, unsafe_allow_html=True)
        else:
            st.info("Sin métricas históricas todavía.")
        
        st.markdown("<h2 class='h-section'>📅 Actividad semanal</h2>", unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        try:
            resp = requests.get(f"{backend_url}/users/{username}/weekly_activity", timeout=10)
            if resp.ok:
                data = resp.json().get("activity", [])
                if data:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    df["minutos"] = df["total_seconds"] / 60.0
                    df["day"] = pd.to_datetime(df["day"])
                    df = df.sort_values("day")
                    mapping = {
                        "Monday": "Lun", "Tuesday": "Mar", "Wednesday": "Mié",
                        "Thursday": "Jue", "Friday": "Vie", "Saturday": "Sáb", "Sunday": "Dom"
                    }
                    df["dia_semana"] = df["day"].dt.day_name().map(mapping)
                    order = ["No inició sesión", "Hasta 5 min", "Hasta 15 min", "Hasta 30 min", "Más de 30 min"]

                    chart = (
                        alt.Chart(df)
                        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                        .encode(
                            x=alt.X("dia_semana:N", title="Día de la semana", sort=["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]),
                            y=alt.Y("minutos:Q", title="Minutos totales"),
                            color=alt.Color(
                                "categoria:N",
                                title="Nivel de actividad",
                                scale=alt.Scale(
                                    domain=order,
                                    range=["#ef4444", "#f97316", "#facc15", "#22c55e", "#3b82f6"]
                                )
                            ),
                            tooltip=[
                                alt.Tooltip("day:T", title="Fecha"),
                                alt.Tooltip("minutos:Q", title="Minutos totales", format=".1f"),
                                alt.Tooltip("categoria:N", title="Nivel")
                            ],
                        )
                        .properties(height=300, width="container")
                    )
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info("Sin datos de actividad aún.")
            else:
                st.warning("No se pudo obtener la actividad semanal.")
        except Exception as e:
            st.warning(f"Error al obtener la actividad: {e}")

    st.markdown("<h2 class='h-section'>Mis documentos</h2>", unsafe_allow_html=True)
    if docs:
        for d in docs:
            title = f"📄 {d['filename']} — {d['uploaded_at']}"
            with st.expander(title, expanded=False):
                cache_key = f"__cache_doc_{d['id']}"
                if cache_key not in st.session_state:
                    _fetch_and_cache_doc_metrics(backend_url, d["id"])

                metrics_list = st.session_state.get(cache_key)
                if metrics_list:
                    latest_by_name = {}
                    for row in metrics_list:
                        latest_by_name[row["metric_name"]] = row["metric_value"]

                    cA, cB = st.columns(2, gap="medium")
                    for i, k in enumerate(SHOW_KEYS):
                        if k in latest_by_name:
                            (cA if i % 2 == 0 else cB).metric(PRETTY[k], pretty_int(latest_by_name[k]))

                del_flag_key = f"__confirm_del_{d['id']}"
                if st.button("❌ Eliminar", key=f"del_{d['id']}", use_container_width=True):
                    st.session_state[del_flag_key] = True

                if st.session_state.get(del_flag_key):
                    st.warning("Esta acción eliminará definitivamente el documento y sus métricas. ¿Confirmas?")
                    col_ok, col_cancel = st.columns(2)
                    if col_ok.button("Sí, eliminar", key=f"ok_{d['id']}", use_container_width=True):
                        try:
                            r = requests.delete(f"{backend_url}/documents/{d['id']}", timeout=15)
                            if r.ok and r.json().get("ok"):
                                deleted_id = d['id']
                                if st.session_state.get("last_doc_id") == deleted_id:
                                    clear_current_analysis()
                                st.session_state.pop(f"__cache_doc_{d['id']}", None)
                                cargar_metricas(username, backend_url)
                                st.session_state[del_flag_key] = False
                                st.rerun()
                            else:
                                st.error(f"No se pudo eliminar: {r.text}")
                        except Exception as e:
                            st.error(f"Error eliminando: {e}")
                    if col_cancel.button("Cancelar", key=f"cancel_{d['id']}", use_container_width=True):
                        st.session_state[del_flag_key] = False
    else:
        st.info("No hay documentos aún.")

def render_status(backend_url):
    if "modelo_listo" not in st.session_state:
        st.session_state["modelo_listo"] = False
    if "status_progress" not in st.session_state:
        st.session_state["status_progress"] = 0
    if "status_message" not in st.session_state:
        st.session_state["status_message"] = "⚡ Preparando…"

    st.progress(st.session_state["status_progress"])

    if st.session_state["modelo_listo"]:
        st.success("✅ Modelo cargado y listo para subir PDFs")
        return

    estado = fetch_status(backend_url, timeout=5)
    st.session_state["modelo_listo"]  = bool(estado.get("modelo_listo"))
    st.session_state["status_progress"] = int(estado.get("progress", 0))
    st.session_state["status_message"]  = estado.get("message", "")
    st.info(st.session_state["status_message"] or "⚡ Cargando…")

    if st.button("🔄 Actualizar estado", key="btn_status_refresh_main", use_container_width=True):
        estado = fetch_status(backend_url, timeout=5)
        st.session_state["modelo_listo"]  = bool(estado.get("modelo_listo"))
        st.session_state["status_progress"] = int(estado.get("progress", 0))
        st.session_state["status_message"]  = estado.get("message", "")

    st.stop()


def main_app():
    st.sidebar.title("Opciones")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")

    if st.session_state.get("logged_in", False):
        st.sidebar.success(f"Sesión iniciada como: {st.session_state['usuario']}")
        inject_session_js(backend_url, st.session_state["usuario"])

        if st.sidebar.button("🔚 Cerrar sesión"):
            try:
                requests.post(f"{backend_url}/users/logout", data={"username": st.session_state['usuario']}, timeout=5)
            except Exception:
                pass
            st.session_state["logged_in"] = False
            st.session_state.pop("usuario", None)
            _clear_status_cache()
            _clear_metrics_cache()
            _clear_input_cache()
            st.rerun()

        if st.sidebar.button("🧹 Limpiar análisis actual"):
            clear_current_analysis()
            st.rerun()

    else:
        st.sidebar.write("No has iniciado sesión.")
        colL, colC = st.sidebar.columns(2)
        if colL.button("🔓 Iniciar sesión"):
            st.session_state["show_login"] = True
            st.session_state["show_create_account"] = False
            st.rerun()
        if colC.button("📝 Crear cuenta"):
            st.session_state["show_create_account"] = True
            st.session_state["show_login"] = False
            st.rerun()

    if st.session_state.get("show_login", False):
        login()
        return
    elif st.session_state.get("show_create_account", False):
        create_account()
        return

    st.title("📝 PALABRIA - Corrector de Textos")

    if "usuario" not in st.session_state:
        st.warning("Por favor, selecciona una opción en la barra lateral.")
        return

    if "load_disparado" not in st.session_state:
        st.session_state["load_disparado"] = False
    if not st.session_state["load_disparado"]:
        try:
            requests.post(f"{backend_url}/load/", timeout=5)
        except Exception:
            pass
        st.session_state["load_disparado"] = True

    st.markdown("<h2 class='h-section'>Estado del modelo</h2>", unsafe_allow_html=True)
    render_status(backend_url)

    if not st.session_state.get("modelo_listo", False):
        return

    st.markdown("<div class='spacer-1cm'></div>", unsafe_allow_html=True)

    st.markdown("<h2 class='h-section'>📤 ANALIZA TU PDF O PEGA TU TEXTO</h2>", unsafe_allow_html=True)

    st.markdown("<h2 class='h-section'>Fuente de entrada</h2>", unsafe_allow_html=True)
    modo_entrada = st.radio(" ", ["Subir PDF", "Escribir texto"], horizontal=True, label_visibility="collapsed")

    texto_plano = None
    uploaded_file = None
    file_bytes = None
    digest = None

    if "last_input_digest" not in st.session_state:
        st.session_state["last_input_digest"] = None
    if "last_doc_id" not in st.session_state:
        st.session_state["last_doc_id"] = None
    if "last_analysis" not in st.session_state:
        st.session_state["last_analysis"] = None

    if modo_entrada == "Subir PDF":
        st.markdown("<h2 class='h-section'>Sube tu PDF</h2>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("", type=["pdf"], label_visibility="collapsed")

        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            digest = hashlib.sha256(file_bytes).hexdigest()

        should_process = (uploaded_file is not None) and (digest != st.session_state.get("last_input_digest"))

        if should_process:
            with st.spinner("Analizando el PDF..."):
                files = {'file': (uploaded_file.name, file_bytes, "application/pdf")}
                data = {'username': st.session_state["usuario"]}
                response = requests.post(f"{backend_url}/process/", files=files, data=data, timeout=120)

            if response.status_code == 200:
                data = response.json()
                st.session_state["last_input_digest"] = digest
                st.session_state["last_pdf_name"] = uploaded_file.name
                st.session_state["last_doc_id"] = data.get("doc_id")
                st.session_state["last_analysis"] = {
                    "original_text": data.get("original_text", ""), 
                    "metricas": data.get("metricas", {}),
                    "corrected_text": data.get("corrected", ""),
                    "feedback": data.get("feedback", "")
                }
                st.session_state["edited_text_area"] = st.session_state["last_analysis"]["corrected_text"]
                st.session_state["__edited_for_doc"] = st.session_state["last_doc_id"]
            else:
                st.error(f"❌ Error al procesar el PDF (código {response.status_code})")
                try:
                    st.code(response.text, language="json")
                except Exception:
                    st.write(response.text)
                st.stop()

    else:
        st.markdown("<h2 class='h-section'>Escribir texto</h2>", unsafe_allow_html=True)
        texto_plano = st.text_area("Pega aquí tu texto", height=200, key="__input_texto_plano")

        default_name = st.session_state.get("__input_filename", "mi_texto.txt")
        nombre_doc = st.text_input("Nombre del documento", value=default_name, key="__input_filename")

        nombre_doc_norm = (nombre_doc or "mi_texto.txt").strip()
        if "." not in nombre_doc_norm:
            nombre_doc_norm += ".txt"

        col_a, col_b = st.columns([1,3])
        if col_a.button("Analizar texto"):
            if not texto_plano or not texto_plano.strip():
                st.warning("Escribe algún texto antes de analizar.")
            else:
                digest = hashlib.sha256((texto_plano or "").encode("utf-8")).hexdigest()
                if digest != st.session_state.get("last_input_digest"):
                    with st.spinner("Analizando el texto..."):
                        data = {
                            'username': st.session_state["usuario"],
                            'text': texto_plano,
                            'filename': nombre_doc_norm,
                        }
                        response = requests.post(f"{backend_url}/process_text/", data=data, timeout=120)

                    if response.status_code == 200:
                        resp = response.json()
                        st.session_state["last_input_digest"] = digest
                        st.session_state["last_pdf_name"] = nombre_doc_norm
                        st.session_state["last_doc_id"] = resp.get("doc_id")
                        st.session_state["last_analysis"] = {
                            "original_text": resp.get("original_text", ""),
                            "metricas": resp.get("metricas", {}),
                            "corrected_text": resp.get("corrected", []),
                            "feedback": resp.get("feedback", "")
                        }
                        st.session_state["edited_text_area"] = st.session_state["last_analysis"]["corrected_text"]
                        st.session_state["__edited_for_doc"] = st.session_state["last_doc_id"]
                    else:
                        st.error(f"❌ Error al procesar el texto (código {response.status_code})")
                        try:
                            st.code(response.text, language="json")
                        except Exception:
                            st.write(response.text)
                        st.stop()

    st.markdown("<div class='spacer-tabs'></div>", unsafe_allow_html=True)

  
    tabs = st.tabs(["📄 Análisis actual", "📊 Métricas globales"])

    with tabs[0]:
        if has_current_analysis():
            anal = st.session_state["last_analysis"]
            metricas = anal.get("metricas", {})
            original_joined = anal.get("original_text") or "\n".join(anal.get("original_sentences", []))
            corrected_text = anal.get("corrected_text", "")

            if st.session_state.get("__edited_for_doc") != st.session_state.get("last_doc_id"):
                st.session_state["edited_text_area"] = corrected_text
                st.session_state["__edited_for_doc"] = st.session_state.get("last_doc_id")

            if "edited_text_area" not in st.session_state:
                st.session_state["edited_text_area"] = corrected_text

            edited_text_current = st.session_state.get("edited_text_area", corrected_text)
            cambios_usuario_total = word_levenshtein_count(original_joined or "", edited_text_current or "")

            if metricas:
                st.markdown("<h2 class='h-section'>📊 Métricas del texto actual</h2>", unsafe_allow_html=True)
                col1, col2 = st.columns(2, gap="medium")
                col1.metric("Total de frases", metricas.get("total_frases", 0))
                col2.metric("Posibles frases con 'tú' impersonal", metricas.get("frases_con_tu_impersonal", 0))
                col3, col4 = st.columns(2, gap="medium")
                col3.metric("Cambios propuestos (modelo)", metricas.get("cambios_propuestos_modelo", 0))
                col4.metric("Cambios realizados (usuario)", cambios_usuario_total)

            st.markdown("<h2 class='h-section'>📥 Texto original (del PDF o entrada de texto)</h2>", unsafe_allow_html=True)

            original_text_display = anal.get("original_text", "")

            st.markdown(
                f"""
                <textarea class="readonly-box" readonly style="white-space: pre-wrap; line-height: 1.5;">{original_text_display.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</textarea>
                """,
                unsafe_allow_html=True
            )

            st.markdown("<h2 class='h-section'>💻 Salida del modelo</h2>", unsafe_allow_html=True)
            st.markdown(
               f"""
                <textarea class="readonly-box" readonly>{(corrected_text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</textarea>
                """,
                unsafe_allow_html=True
            )

            st.markdown("<h2 class='h-section'>📚 Feedback del modelo</h2>", unsafe_allow_html=True)
            
            feedback_text = anal.get("feedback", "")
            st.markdown(f"""<textarea class="readonly-box" readonly style="white-space: pre-wrap; line-height: 1.5;">{feedback_text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</textarea>""", unsafe_allow_html=True)

            st.markdown("<h2 class='h-section'>📝 Revisa y edita el texto corregido</h2>", unsafe_allow_html=True)

            def _save_user_changes_callback():
                edited_now = st.session_state.get("edited_text_area", "")
                changes_now = word_levenshtein_count(original_joined or "", edited_now or "")
                last_saved = st.session_state.get(f"__last_saved_changes_{st.session_state.get('last_doc_id')}")
                if last_saved is None or int(last_saved) != int(changes_now):
                    _post_user_changes(backend_url, st.session_state["last_doc_id"], int(changes_now))

            edited_text = st.text_area(
                "Tu versión final",
                key="edited_text_area",
                height=300,
                on_change=_save_user_changes_callback,
            )

            if st.button("📅 Descargar PDF corregido"):
                base = (st.session_state.get("last_pdf_name") or "Texto_Corregido").rsplit(".", 1)[0]
                pdf_filename = f"{base}.pdf"
                pdf_filename = save_text_as_pdf(edited_text, filename=pdf_filename)
                with open(pdf_filename, "rb") as file:
                    st.download_button("Descargar el PDF", file, file_name=pdf_filename, mime="application/pdf")
        else:
            st.info("No hay análisis activo. Sube un PDF o escribe texto y pulsa “Analizar texto”.")

    with tabs[1]:
        ver_mis_metricas(st.session_state["usuario"], backend_url)

if __name__ == "__main__":
    main_app()