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

st.set_page_config(page_title="PALABRIA", layout="centered", initial_sidebar_state="expanded")

PRETTY = {
    "total_frases": "Total de frases",
    "frases_con_tu_impersonal": "Posibles frases con 'tú' impersonal",
    "cambios_propuestos_modelo": "Cambios propuestos (modelo)",
    "cambios_realizados_usuario": "Cambios realizados (usuario)",
}
SHOW_KEYS = list(PRETTY.keys())

# ── DESIGN SYSTEM ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;500;600;700;800&display=swap');

/* ── Variables ── */
:root {
  --navy:        #1a2e4a;
  --navy-mid:    #243c5e;
  --navy-soft:   #2e4d78;
  --blue:        #2563eb;
  --blue-light:  #3b82f6;
  --blue-pale:   #eff6ff;
  --blue-border: #bfdbfe;
  --slate:       #4a5f78;
  --slate-light: #7a93b0;
  --bg:          #f4f7fb;
  --surface:     #ffffff;
  --border:      #dde6f0;
  --text:        #1a2e4a;
  --text-soft:   #4a5f78;
  --text-muted:  #8aa0b8;
  --success:     #16a34a;
  --warning:     #d97706;
  --error:       #dc2626;
  --radius:      10px;
  --radius-sm:   6px;
  --shadow-sm:   0 1px 3px rgba(26,46,74,0.08);
  --shadow-md:   0 4px 14px rgba(26,46,74,0.10);
  --shadow-lg:   0 8px 32px rgba(26,46,74,0.13);
  --transition:  0.18s ease;
}

/* ── Global ── */
html, body, [class*="css"] {
  font-family: 'Nunito', sans-serif !important;
  color: var(--text) !important;
  background-color: var(--bg) !important;
}
.stApp { background: var(--bg) !important; }
.block-container {
  padding-top: 2.2rem !important;
  padding-bottom: 3rem !important;
  max-width: 860px !important;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
  box-sizing: border-box !important;
}

/* Forzar que el gráfico no se salga */
div[data-testid="stVegaLiteChart"] > div,
div[data-testid="stVegaLiteChart"] canvas,
div[data-testid="stVegaLiteChart"] svg {
  max-width: 100% !important;
  width: 100% !important;
  overflow: hidden !important;
}

/* Ocultar botón colapsar sidebar */
button[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[aria-label="Close sidebar"],
button[aria-label="Collapse sidebar"] { display: none !important; }

/* ── Sidebar wrapper ── */
section[data-testid="stSidebar"] {
  background: var(--navy) !important;
  border-right: none !important;
  width: 240px !important;
  min-width: 240px !important;
  max-width: 240px !important;
}
section[data-testid="stSidebar"] > div:first-child {
  padding: 2rem 1.2rem 1.5rem 1.2rem !important;
  box-sizing: border-box !important;
}
section[data-testid="stSidebar"] * {
  color: #c8d8ea !important;
  font-family: 'Nunito', sans-serif !important;
}

/* Título sidebar */
section[data-testid="stSidebar"] h1 {
  font-size: 1.4rem !important;
  font-weight: 800 !important;
  color: #ffffff !important;
  letter-spacing: 0.04em !important;
  white-space: nowrap !important;
  overflow: visible !important;
  padding-bottom: 0.9rem !important;
  border-bottom: 1px solid rgba(255,255,255,0.12) !important;
  margin-bottom: 1.3rem !important;
  margin-top: 0 !important;
}

/* Éxito / usuario logado */
section[data-testid="stSidebar"] .stSuccess {
  background: rgba(37,99,235,0.18) !important;
  border: 1px solid rgba(59,130,246,0.35) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 0.9rem !important;
  font-weight: 600 !important;
  color: #93c5fd !important;
  padding: 0.6rem 1rem !important;
  margin-bottom: 0.4rem !important;
  min-height: 2.55rem !important;
  width: 100% !important;
  display: flex !important;
  align-items: center !important;
  box-sizing: border-box !important;
}

/* Botones sidebar — ancho completo, texto visible */
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div,
section[data-testid="stSidebar"] .stButton,
section[data-testid="stSidebar"] .element-container,
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"],
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div {
  width: 100% !important;
  box-sizing: border-box !important;
  min-width: 0 !important;
}
section[data-testid="stSidebar"] .stButton > button {
  background: rgba(255,255,255,0.07) !important;
  border: 1px solid rgba(255,255,255,0.15) !important;
  color: #e0eaf5 !important;
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.85rem !important;
  font-weight: 600 !important;
  border-radius: var(--radius-sm) !important;
  padding: 0.55rem 0.6rem !important;
  height: auto !important;
  min-height: 2.4rem !important;
  width: 100% !important;
  text-align: center !important;
  transition: var(--transition) !important;
  margin-bottom: 0.4rem !important;
  box-shadow: none !important;
  box-sizing: border-box !important;
  white-space: normal !important;
  overflow: visible !important;
  word-break: break-word !important;
  line-height: 1.3 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(37,99,235,0.28) !important;
  border-color: rgba(59,130,246,0.55) !important;
  color: #ffffff !important;
  transform: none !important;
  box-shadow: none !important;
}

/* ── Page title ── */
h1 {
  font-family: 'Nunito', sans-serif !important;
  font-size: 2rem !important;
  font-weight: 800 !important;
  color: var(--navy) !important;
  letter-spacing: -0.01em !important;
  line-height: 1.2 !important;
  text-align: center !important;
}

/* ── Section headings ── */
.palabria-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Nunito', sans-serif;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--blue);
  margin-top: 1.8rem;
  margin-bottom: 0.7rem;
}
.palabria-section::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--blue-border);
}

/* ── Divider ── */
.palabria-rule {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1.4rem 0;
}

/* ── Metric cards ── */
div[data-testid="stMetric"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-top: 3px solid var(--blue) !important;
  border-radius: var(--radius) !important;
  padding: 0.45rem 0.75rem 0.4rem !important;
  box-shadow: var(--shadow-sm) !important;
  transition: var(--transition) !important;
}
div[data-testid="stMetric"]:hover {
  box-shadow: var(--shadow-md) !important;
  border-color: var(--blue-light) !important;
  transform: translateY(-1px);
}
div[data-testid="stMetricLabel"] {
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.67rem !important;
  font-weight: 700 !important;
  color: var(--text-muted) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  margin-bottom: 0.1rem !important;
}
div[data-testid="stMetricValue"] {
  font-family: 'Nunito', sans-serif !important;
  font-size: 1.05rem !important;
  font-weight: 800 !important;
  color: var(--navy) !important;
  line-height: 1.2 !important;
}
div[data-testid="stMetricDelta"] { display: none !important; }

/* ── Buttons ── */
.stButton > button {
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.88rem !important;
  font-weight: 700 !important;
  background: var(--blue) !important;
  color: #ffffff !important;
  border: none !important;
  border-radius: var(--radius-sm) !important;
  padding: 0.55rem 1.4rem !important;
  box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
  transition: var(--transition) !important;
  letter-spacing: 0.01em !important;
}
.stButton > button:hover {
  background: var(--navy-soft) !important;
  box-shadow: 0 4px 14px rgba(37,99,235,0.32) !important;
  transform: translateY(-1px) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── Download button ── */
.stDownloadButton > button {
  background: transparent !important;
  color: var(--blue) !important;
  border: 2px solid var(--blue) !important;
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.88rem !important;
  font-weight: 700 !important;
  border-radius: var(--radius-sm) !important;
  padding: 0.5rem 1.3rem !important;
  transition: var(--transition) !important;
}
.stDownloadButton > button:hover {
  background: var(--blue-pale) !important;
  box-shadow: var(--shadow-sm) !important;
}

/* ── Inputs ── */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.95rem !important;
  font-weight: 500 !important;
  background: var(--surface) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius) !important;
  color: var(--text) !important;
  padding: 0.6rem 0.85rem !important;
  transition: var(--transition) !important;
  box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
  border-color: var(--blue) !important;
  box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
  outline: none !important;
}
div[data-testid="stTextArea"] textarea {
  resize: vertical !important;
  line-height: 1.65 !important;
}

/* ── Labels ── */
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label,
div[data-testid="stFileUploader"] label,
div[data-testid="stRadio"] label {
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.8rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.05em !important;
  text-transform: uppercase !important;
  color: var(--text-soft) !important;
}

/* ── Radio ── */
div[data-testid="stRadio"] > div {
  gap: 0.5rem !important;
  flex-direction: row !important;
}
div[data-testid="stRadio"] > div label {
  background: var(--surface) !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  padding: 0.4rem 1rem !important;
  font-size: 0.88rem !important;
  font-weight: 600 !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  color: var(--text-soft) !important;
  cursor: pointer !important;
  transition: var(--transition) !important;
}
div[data-testid="stRadio"] > div label:has(input:checked) {
  background: var(--blue-pale) !important;
  border-color: var(--blue) !important;
  color: var(--blue) !important;
  font-weight: 700 !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 2px solid var(--border) !important;
  gap: 0 !important;
  padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.88rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.04em !important;
  color: var(--text-muted) !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  margin-bottom: -2px !important;
  padding: 0.7rem 1.5rem !important;
  border-radius: 0 !important;
  transition: var(--transition) !important;
  text-transform: uppercase !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--navy) !important; }
.stTabs [aria-selected="true"] {
  color: var(--blue) !important;
  border-bottom: 2px solid var(--blue) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.4rem !important; }

/* ── File uploader ── */
div[data-testid="stFileUploader"] {
  background: var(--surface) !important;
  border: 2px dashed var(--blue-border) !important;
  border-radius: var(--radius) !important;
  padding: 1.2rem !important;
  transition: var(--transition) !important;
}
div[data-testid="stFileUploader"]:hover {
  border-color: var(--blue) !important;
  background: var(--blue-pale) !important;
}

/* ── Alerts ── */
div[data-testid="stAlert"] {
  border-radius: var(--radius) !important;
  border: none !important;
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.9rem !important;
  font-weight: 500 !important;
}
.stSuccess {
  background: #f0fdf4 !important;
  border-left: 4px solid var(--success) !important;
}
.stWarning {
  background: #fffbeb !important;
  border-left: 4px solid var(--warning) !important;
}
.stError {
  background: #fef2f2 !important;
  border-left: 4px solid var(--error) !important;
}
.stInfo {
  background: var(--blue-pale) !important;
  border-left: 4px solid var(--blue-border) !important;
}

/* ── Progress bar ── */
div[data-testid="stProgress"] > div > div {
  background: linear-gradient(90deg, var(--blue), var(--blue-light)) !important;
  border-radius: 99px !important;
}
div[data-testid="stProgress"] > div {
  background: var(--border) !important;
  border-radius: 99px !important;
  height: 5px !important;
}

/* ── Expander ── */
details[data-testid="stExpander"] {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow-sm) !important;
  margin-bottom: 0.5rem !important;
  overflow: hidden !important;
}
details[data-testid="stExpander"] summary {
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.9rem !important;
  font-weight: 600 !important;
  color: var(--text-soft) !important;
  padding: 0.8rem 1rem !important;
}
details[data-testid="stExpander"] summary:hover { color: var(--navy) !important; }
details[data-testid="stExpander"] > div {
  padding: 0.5rem 1rem 1rem !important;
  border-top: 1px solid var(--border) !important;
}

/* ── Read-only boxes ── */
.readonly-box {
  width: 100% !important;
  box-sizing: border-box !important;
  background: #f8fafc !important;
  border: 1.5px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 0.85rem 1rem !important;
  font-family: 'Nunito', sans-serif !important;
  font-size: 0.92rem !important;
  font-weight: 400 !important;
  line-height: 1.7 !important;
  color: var(--text-soft) !important;
  min-height: 130px !important;
  max-height: 280px !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  resize: none !important;
  white-space: pre-wrap !important;
}

/* ── Metric table rows ── */
.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.1rem;
  border-radius: var(--radius-sm);
  font-size: 1rem;
  font-family: 'Nunito', sans-serif;
  transition: var(--transition);
}
.metric-row:nth-child(odd)  { background: #f4f7fb; }
.metric-row:nth-child(even) { background: var(--surface); }
.metric-row:hover           { background: var(--blue-pale); }
.metric-label { font-weight: 500; color: var(--text-soft); font-size: 0.97rem; }
.metric-value { font-weight: 800; color: var(--navy); font-size: 1.05rem; }

/* ── Columns ── */
div[data-testid="stHorizontalBlock"] { gap: 0.75rem !important; }

/* ── Altair chart ── */
div[data-testid="stVegaLiteChart"] {
  border-radius: var(--radius) !important;
  overflow: hidden !important;
  box-shadow: var(--shadow-md) !important;
  margin: 1rem 0 1rem 0 !important;
  border: 1px solid var(--border) !important;
  background: var(--surface) !important;
  padding: 2rem 2rem 0.5rem 2rem !important;
}

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: var(--blue-light); }
</style>
""", unsafe_allow_html=True)


# ── HELPERS ────────────────────────────────────────────────────────────────────

def section(icon: str, label: str):
    st.markdown(
        f"<div class='palabria-section'><span>{icon}</span> {label}</div>",
        unsafe_allow_html=True
    )

def rule():
    st.markdown("<hr class='palabria-rule'>", unsafe_allow_html=True)

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
    if not text:
        return ""
    t = text
    t = t.replace("…", "...")
    t = (
        t.replace("\u201c", '"')
         .replace("\u201d", '"')
    )
    t = (
        t.replace("\u2018", "'")
         .replace("\u2019", "'")
    )
    t = (
        t.replace("\u2014", "-")
         .replace("\u2013", "-")
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
    st.markdown("""
<style>
div[data-testid="stForm"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem 2rem 1.5rem 2rem;
    box-shadow: var(--shadow-md);
    max-width: 480px;
    margin: 4.5rem auto 0 auto;
}
</style>
""", unsafe_allow_html=True)
    with st.form("login_form"):
        section("🔓", "Iniciar sesión")
        username = st.text_input("Nombre de usuario")
        submit = st.form_submit_button("Entrar", use_container_width=True)
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
    st.markdown("""
<style>
div[data-testid="stForm"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem 2rem 1.5rem 2rem;
    box-shadow: var(--shadow-md);
    max-width: 480px;
    margin: 4.5rem auto 0 auto;
}
</style>
""", unsafe_allow_html=True)
    with st.form("create_account_form"):
        section("🔏", "Crear nueva cuenta")
        new_username = st.text_input("Elige un nombre de usuario (letras/números/_-. máx 32)")
        submit = st.form_submit_button("Crear cuenta", use_container_width=True)
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
    section("◈", "Estadísticas globales")

    if "__cache_overview" not in st.session_state or "__cache_documents" not in st.session_state:
        try:
            cargar_metricas(username, backend_url)
            for d in st.session_state.get("__cache_documents", []):
                _fetch_and_cache_doc_metrics(backend_url, d["id"])
        except Exception as e:
            st.error(f"No se pudieron cargar las métricas: {e}")

    if st.button("Actualizar métricas", key="btn_refresh_metrics", use_container_width=True):
        cargar_metricas(username, backend_url)
        for d in st.session_state.get("__cache_documents", []):
            _fetch_and_cache_doc_metrics(backend_url, d["id"])

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

        rule()
        section("▸", "Promedios históricos por métrica")
        avg_metrics = ov.get("avg_metrics", {})
        if avg_metrics:
            html_rows = ""
            for key in SHOW_KEYS:
                if key in avg_metrics:
                    label = PRETTY.get(key, key)
                    value = pretty_int(round(avg_metrics[key], 2))
                    html_rows += f"<div class='metric-row'><span class='metric-label'>{label}</span><span class='metric-value'>{value}</span></div>"
            st.markdown(html_rows, unsafe_allow_html=True)
        else:
            st.info("Sin métricas históricas todavía.")

        rule()
        section("◈", "Actividad semanal")
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

    rule()
    section("☰", "Mis documentos")
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
        st.sidebar.markdown("<p style='color:#8aa0b8;font-size:0.82rem;font-family:Nunito,sans-serif;margin-bottom:0.6rem;'>No has iniciado sesión.</p>", unsafe_allow_html=True)
        if st.sidebar.button("🔓 Iniciar sesión", use_container_width=True):
            st.session_state["show_login"] = True
            st.session_state["show_create_account"] = False
            st.rerun()
        if st.sidebar.button("🔏 Crear cuenta", use_container_width=True):
            st.session_state["show_create_account"] = True
            st.session_state["show_login"] = False
            st.rerun()

    if st.session_state.get("show_login", False):
        login()
        return
    elif st.session_state.get("show_create_account", False):
        create_account()
        return

    if "usuario" not in st.session_state:
        # ── Pantalla de bienvenida con fondo de hoja rayada ────────────────
        st.markdown("""
<style>
.palabria-welcome {
    background-color: #fffef7;
    background-image: linear-gradient(#c8d8ea 1px, transparent 1px);
    background-size: 100% 2.2rem;
    border: 1px solid #dde6f0;
    border-left: 6px solid #2563eb;
    border-radius: 14px;
    padding: 4rem 2.5rem 3.2rem 2.5rem;
    margin: 4.5rem auto 0 auto;
    max-width: 680px;
    box-shadow: 0 8px 32px rgba(26,46,74,0.10);
    text-align: center;
}
.palabria-welcome-title {
    font-family: 'Nunito', sans-serif;
    font-size: 4rem;
    font-weight: 800;
    color: #1a2e4a;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin: 0 0 0.5rem 0;
}
.palabria-welcome-sub {
    font-family: 'Nunito', sans-serif;
    font-size: 1.05rem;
    font-weight: 500;
    color: #4a5f78;
    margin: 0 0 2rem 0;
}
.palabria-welcome-hint {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 99px;
    padding: 0.45rem 1.2rem;
    font-family: 'Nunito', sans-serif;
    font-size: 0.88rem;
    font-weight: 700;
    color: #2563eb;
}
</style>
<div class="palabria-welcome">
    <div class="palabria-welcome-title">📝 PALABRIA</div>
    <div class="palabria-welcome-sub">Corrector de escritura académica con IA</div>
    <div class="palabria-welcome-hint">← Inicia sesión o crea una cuenta para comenzar</div>
</div>
""", unsafe_allow_html=True)
        return

    st.title("📝 PALABRIA")

    if "load_disparado" not in st.session_state:
        st.session_state["load_disparado"] = False
    if not st.session_state["load_disparado"]:
        try:
            requests.post(f"{backend_url}/load/", timeout=5)
        except Exception:
            pass
        st.session_state["load_disparado"] = True

    section("◎", "Estado del modelo")
    render_status(backend_url)

    if not st.session_state.get("modelo_listo", False):
        return

    section("▲", "Analiza tu texto")
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
        texto_plano = st.text_area("Pega aquí tu texto", height=200, key="__input_texto_plano")

        default_name = st.session_state.get("__input_filename", "mi_texto.txt")
        nombre_doc = st.text_input("Nombre del documento", value=default_name, key="__input_filename")

        nombre_doc_norm = (nombre_doc or "mi_texto.txt").strip()
        if "." not in nombre_doc_norm:
            nombre_doc_norm += ".txt"

        col_a, col_b = st.columns([1, 3])
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
                section("◈", "Métricas del texto")
                col1, col2 = st.columns(2, gap="medium")
                col1.metric("Total de frases", metricas.get("total_frases", 0))
                col2.metric("Posibles frases con 'tú' impersonal", metricas.get("frases_con_tu_impersonal", 0))
                col3, col4 = st.columns(2, gap="medium")
                col3.metric("Cambios propuestos (modelo)", metricas.get("cambios_propuestos_modelo", 0))
                col4.metric("Cambios realizados (usuario)", cambios_usuario_total)

            rule()
            section("▸", "Texto original")
            original_text_display = anal.get("original_text", "")
            st.markdown(
                f"""<textarea class="readonly-box" readonly style="white-space: pre-wrap; line-height: 1.5;">{original_text_display.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</textarea>""",
                unsafe_allow_html=True
            )

            section("◎", "Salida del modelo")
            st.markdown(
                f"""<textarea class="readonly-box" readonly>{(corrected_text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</textarea>""",
                unsafe_allow_html=True
            )

            section("✦", "Feedback del modelo")
            feedback_text = anal.get("feedback", "")
            st.markdown(
                f"""<textarea class="readonly-box" readonly style="white-space: pre-wrap; line-height: 1.5;">{feedback_text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}</textarea>""",
                unsafe_allow_html=True
            )

            rule()
            section("✎", "Edita tu versión final")

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

            if st.button("📥 Descargar PDF corregido"):
                base = (st.session_state.get("last_pdf_name") or "Texto_Corregido").rsplit(".", 1)[0]
                pdf_filename = f"{base}.pdf"
                pdf_filename = save_text_as_pdf(edited_text, filename=pdf_filename)
                with open(pdf_filename, "rb") as file:
                    st.download_button("Descargar el PDF", file, file_name=pdf_filename, mime="application/pdf")
        else:
            st.info("No hay análisis activo. Sube un PDF o escribe texto y pulsa «Analizar texto».")

    with tabs[1]:
        ver_mis_metricas(st.session_state["usuario"], backend_url)

if __name__ == "__main__":
    main_app()
