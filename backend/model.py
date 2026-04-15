# backend/model.py
import gc
import re
import time
import threading
from typing import List, Optional

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


# ── Estado global ──────────────────────────────────────────────────────────────
MODEL_LOADED: bool = False
LOAD_PROGRESS: int = 0
LOAD_MESSAGE: str = "Modelo no cargado."

_lock   = threading.Lock()
_thread = None

_tokenizer: Optional[AutoTokenizer]         = None
_model:     Optional[AutoModelForCausalLM]  = None

# ── Feedback jobs asíncronos ───────────────────────────────────────────────────
# doc_id → {"status": "pending"|"done"|"error", "result": str}
_feedback_jobs: dict = {}
_feedback_lock  = threading.Lock()

# ── Modelo ─────────────────────────────────────────────────────────────────────
MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"

# ── Parámetros de generación ───────────────────────────────────────────────────
MAX_NEW_TOKENS_CORRECTION = 1024  # texto completo — escala dinámicamente
MAX_NEW_TOKENS_FEEDBACK   = 300   # feedback por documento
MAX_NEW_TOKENS_GLOBAL     = 350   # valoración global
DO_SAMPLE          = False
NUM_BEAMS          = 1

# ── Prompts de corrección — optimizados para Llama 3.2 3B Instruct ─────────────
# Llama 3.2 3B — texto completo en UNA sola llamada (como el original del ZIP).
# Mucho más rápido que frase a frase. El modelo corrige solo donde hay tú
# impersonal y deja el resto exactamente igual.
SYSTEM_PROMPT_CORRECTION = (
    "Eres un corrector gramatical de español escrito formal. "
    "Corrige SOLO los usos impersonales genéricos de la segunda persona del singular ('tú'): "
    "sustitúyelos por construcciones impersonales con 'se'. "
    "Solo usa 'uno' si 'se' es gramaticalmente inadecuado o queda poco natural. "
    "NO corrijas si 'tú' se refiere a una persona concreta con nombre, está entre comillas "
    "o forma parte de discurso directo. No cambies nada más. Devuelve solo el texto corregido."
)

USER_PROMPT_CORRECTION = (
    "Corrige SOLO el 'tú' impersonal genérico del siguiente texto. "
    "Usa 'se' en todos los casos. Solo usa 'uno' si 'se' es gramaticalmente inadecuado o poco natural. "
    "No modifiques nada que esté entre comillas (\", «», ''). "
    "Deja todo lo demás exactamente igual.\n\n"
    "Ejemplo de entrada:\n"
    "Cuando analizas los resultados, puedes cometer errores. "
    "Se observa cómo suben los precios. Laura dijo: \"cuando publicas, tú asumes la responsabilidad.\"\n"
    "Ejemplo de salida:\n"
    "Cuando se analizan los resultados, se pueden cometer errores. "
    "Se observa cómo suben los precios. Laura dijo: \"cuando publicas, tú asumes la responsabilidad.\"\n\n"
    "Texto:\n"
    "{text}\n\n"
    "Texto corregido:"
)

# ── Prompt feedback por documento ──────────────────────────────────────────────
SYSTEM_PROMPT_FEEDBACK = (
    "Eres un tutor de escritura académica en español. "
    "Recibes frases corregidas por uso impersonal del 'tú'. "
    "Escribe un feedback pedagógico en prosa, máximo 2 párrafos cortos, sin listas. "
    "Explica brevemente que el error consiste en usar la segunda persona singular con valor general "
    "y por qué no es adecuado en textos académicos, donde se prefieren construcciones impersonales con 'se'. "
    "Incluye: una explicación clara del fenómeno, una regla fácil de recordar y una frase final de motivación. "
    "Si mencionas ejemplos, usa solo fragmentos reales de las frases recibidas y no inventes casos nuevos. "
    "Tono cercano y profesional, sin ser condescendiente."
)

USER_PROMPT_FEEDBACK = (
    "Se han detectado {n_errores} frase(s) con posible 'tú' impersonal. "
    "Estas son las correcciones:\n\n"
    "{ejemplos}\n\n"
    "Genera el feedback usando solo esta información."
)

# ── Prompt valoración global ───────────────────────────────────────────────────

SYSTEM_PROMPT_GLOBAL = (
    "Eres un tutor de escritura académica en español. "
    "Tu tarea es dar una valoración global breve, motivadora y constructiva del progreso del estudiante "
    "basándote en sus métricas de uso de la aplicación. "
    "Habla directamente al estudiante usando la segunda persona (tú), no uses 'el estudiante' ni tercera persona. "
    "Mantén un tono positivo y de apoyo incluso cuando los resultados sean bajos. "
    "En escritura académica, el uso impersonal de la segunda persona singular ('tú impersonal') se considera inadecuado, "
    "por lo que un porcentaje alto indica que todavía hay aspectos que mejorar, pero debes comentarlo de forma motivadora, "
    "valorando el esfuerzo y animando a seguir practicando. "
    "Máximo dos párrafos cortos."
)

USER_PROMPT_GLOBAL = (
    "Has procesado {total_docs} documentos en {login_days} días de uso.\n"
    "En el {pct_tu:.1f}% de tus documentos se detectó uso del 'tú' impersonal.\n"
    "En el {pct_sin_cambios:.1f}% de tus documentos no realizaste cambios manuales sobre la corrección del modelo.\n"
    "Tiempo medio de sesión: {avg_session}.\n\n"
    "Escribe una valoración motivadora de mi progreso y dame una recomendación concreta para mejorar, "
    "teniendo en cuenta que el 'tú' impersonal es un error que se debe evitar en textos académicos."
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _set(progress: int, message: str):
    global LOAD_PROGRESS, LOAD_MESSAGE
    with _lock:
        LOAD_PROGRESS = max(0, min(100, int(progress)))
        LOAD_MESSAGE  = message


def _clear_cache():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def clean_pred(text: str) -> str:
    """
    Limpia la salida de Llama 3.2 3B Instruct para texto completo.
    Elimina prefijos tipo 'Corrected text:', 'Output:', artefactos iniciales.
    """
    text = text.strip()

    # Si el modelo repite "Corrected text:" o "Output:", quedarse con lo que hay después
    for prefix in (r'texto\s+corregido\s*:', r'corrected\s+text\s*:', r'output\s*:', r'texto\s*:'):
        m = re.search(prefix, text, re.IGNORECASE)
        if m:
            text = text[m.end():].strip()
            break

    # Eliminar prefijos residuales al inicio
    text = re.sub(r'^[\s\-–—]+', '', text)
    text = re.sub(
        r'^(corrección|corregido|input|sentence)\s*:\s*',
        '', text, flags=re.IGNORECASE
    )

    return text.strip().strip('"\'')



# ── Carga del modelo ───────────────────────────────────────────────────────────

def _load_impl():
    global MODEL_LOADED, _tokenizer, _model
    MODEL_LOADED = False
    _clear_cache()

    try:
        _set(5, "Inicializando carga…")

        _set(20, "Preparando configuración del modelo…")

        _set(40, "Cargando tokenizer…")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True)
        if _tokenizer.pad_token is None:
            _tokenizer.pad_token = _tokenizer.eos_token

        _set(75, "Cargando modelo (esto puede tardar)…")
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            device_map="auto",
            torch_dtype=torch.bfloat16,   # bfloat16 completo — más rápido que NF4 en A100
        )
        _model.eval()

        # Asegurar que use_cache está activo (KV-cache → tokens sucesivos más rápidos)
        if hasattr(_model, "config"):
            _model.config.use_cache = True

        _set(95, "Finalizando…")
        time.sleep(0.3)
        MODEL_LOADED = True
        _set(100, "✅ Modelo cargado y listo")

    except Exception as e:
        _set(0, f"❌ Error cargando modelo: {e}")
        MODEL_LOADED = False


def ensure_model_loaded(async_load: bool = True):
    global _thread
    if MODEL_LOADED and _model is not None and _tokenizer is not None:
        return
    if _thread and _thread.is_alive():
        return
    if async_load:
        _thread = threading.Thread(target=_load_impl, daemon=True)
        _thread.start()
    else:
        _load_impl()


# ── Inferencia base ────────────────────────────────────────────────────────────

@torch.inference_mode()
def _chat_generate(messages: list, max_new_tokens: int) -> str:
    """Genera texto a partir de una lista de mensajes chat."""
    global _tokenizer, _model
    if not MODEL_LOADED or _tokenizer is None or _model is None:
        return ""

    enc = _tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
        truncation=True,
        max_length=2048,          # limitar prompt largo → menos tokens de entrada
    )
    input_ids      = enc["input_ids"].to(_model.device)
    attention_mask = enc["attention_mask"].to(_model.device)
    input_length   = input_ids.shape[1]

    output_ids = _model.generate(
        input_ids,
        attention_mask=attention_mask,
        max_new_tokens=max_new_tokens,
        do_sample=DO_SAMPLE,
        num_beams=NUM_BEAMS,
        pad_token_id=_tokenizer.eos_token_id,
        eos_token_id=_tokenizer.eos_token_id,
        use_cache=True,
    )

    generated = output_ids[0][input_length:]
    return _tokenizer.decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    ).strip()


# ── Corrección — texto completo en una sola llamada ───────────────────────────

def correct_full_text(text: str) -> str:
    """
    Corrige el texto completo en UNA sola llamada al modelo.
    Igual que el original del ZIP — mucho más rápido que frase a frase.
    El modelo recibe el texto completo y devuelve el texto corregido.
    """
    if not text or not text.strip():
        return ""
    if not MODEL_LOADED:
        raise RuntimeError("El modelo aún no está cargado.")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_CORRECTION},
        {"role": "user",   "content": USER_PROMPT_CORRECTION.format(text=text.strip())},
    ]
    # max_new_tokens proporcional al texto: ~1.2 tokens por palabra estimado
    n_words = len(text.split())
    max_tok = min(max(n_words * 2, 256), 1024)

    raw = _chat_generate(messages, max_new_tokens=max_tok)
    return clean_pred(raw) if raw else text


# Alias para compatibilidad con main.py existente
def correct_text(sentences: List[str], batch_size: int = 4, max_new_tokens: int = 150) -> List[str]:
    text = " ".join(s.strip() for s in sentences if isinstance(s, str) and s.strip())
    return [correct_full_text(text)]


# ── Feedback por documento ─────────────────────────────────────────────────────

def generate_feedback(original: str, corrected: str, n_errores: int = 0) -> str:
    """Genera feedback pedagógico de forma síncrona (uso interno y global_feedback)."""
    if not MODEL_LOADED or not original.strip():
        return ""

    if original.strip() == corrected.strip():
        return (
            "¡Excelente trabajo! No se ha detectado ningún uso del 'tú' impersonal en este texto. "
            "Las construcciones impersonales están bien empleadas y el registro académico es el adecuado. "
            "Sigue así."
        )

    from backend.utils import split_into_sentences
    orig_sents = split_into_sentences(original)
    corr_sents = split_into_sentences(corrected)

    ejemplos = []
    for o, c in zip(orig_sents, corr_sents):
        if o.strip() != c.strip():
            ejemplos.append(f"• Original:  {o.strip()}\n  Corregida: {c.strip()}")
        if len(ejemplos) >= 3:
            break

    ejemplos_txt = "\n\n".join(ejemplos) if ejemplos else "(No se pudieron extraer ejemplos concretos.)"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_FEEDBACK},
        {"role": "user",   "content": USER_PROMPT_FEEDBACK.format(
            n_errores=n_errores,
            ejemplos=ejemplos_txt,
        )},
    ]
    return _chat_generate(messages, max_new_tokens=MAX_NEW_TOKENS_FEEDBACK)


def schedule_feedback(doc_id: int, original: str, corrected: str, n_errores: int = 0):
    """
    Lanza la generación de feedback en un hilo background.
    La corrección ya se devolvió al usuario; este hilo genera el feedback
    sin bloquear la respuesta HTTP.
    El resultado queda en _feedback_jobs[doc_id] para consultarlo por polling.
    """
    with _feedback_lock:
        _feedback_jobs[doc_id] = {"status": "pending", "result": ""}

    def _run():
        try:
            result = generate_feedback(original, corrected, n_errores)
            with _feedback_lock:
                _feedback_jobs[doc_id] = {"status": "done", "result": result}
        except Exception as e:
            with _feedback_lock:
                _feedback_jobs[doc_id] = {"status": "error", "result": str(e)}

    threading.Thread(target=_run, daemon=True).start()


def get_feedback_status(doc_id: int) -> dict:
    """Devuelve el estado del job de feedback para un doc_id."""
    with _feedback_lock:
        return dict(_feedback_jobs.get(doc_id, {"status": "not_found", "result": ""}))


# ── Valoración global ──────────────────────────────────────────────────────────

def generate_global_feedback(
    total_docs: int,
    login_days: int,
    pct_tu: float,
    pct_sin_cambios: float,
    avg_session_seconds: float,
) -> str:
    """
    Genera una valoración global del progreso del estudiante
    a partir de sus métricas agregadas.
    Solo se llama bajo demanda (botón en el frontend).
    """
    if not MODEL_LOADED:
        return ""

    def _fmt_time(secs: float) -> str:
        s = int(round(secs))
        h, rem = divmod(s, 3600)
        m, ss  = divmod(rem, 60)
        if h > 0:
            return f"{h} h {m} min"
        if m > 0:
            return f"{m} min {ss} s"
        return f"{ss} s"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_GLOBAL},
        {"role": "user",   "content": USER_PROMPT_GLOBAL.format(
            total_docs=total_docs,
            login_days=login_days,
            pct_tu=pct_tu,
            pct_sin_cambios=pct_sin_cambios,
            avg_session=_fmt_time(avg_session_seconds),
        )},
    ]
    return _chat_generate(messages, max_new_tokens=MAX_NEW_TOKENS_GLOBAL)