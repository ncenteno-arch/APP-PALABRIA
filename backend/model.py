# backend/model.py
import time
import threading
from typing import List, Optional

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


MODEL_LOADED: bool = False
LOAD_PROGRESS: int = 0
LOAD_MESSAGE: str = "Modelo no cargado."

_lock = threading.Lock()
_thread = None

_tokenizer: Optional[AutoTokenizer] = None
_model: Optional[AutoModelForCausalLM] = None

MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"

PROMPT_TEMPLATE = """<s>[INST] <<SYS>>
Tu función es corregir textos bajo estas dos condiciones simultáneas:
- Corrige todos los errores ortográficos y de puntuación.
- Transforma el "tú" impersonal en "se" impersonal (ej: "cuando hablas" -> "cuando se habla"). 

REGLAS:
- Mantén la concordancia: si el objeto es plural, el verbo va en plural (ej: "si vendes manzanas" -> "se venden manzanas").
- No modifiques el "tú" si es una apelación directa a una persona real.
- No añadidas introducciones, explicaciones ni comentarios. Entrega solo el resultado.
<</SYS>>

Ejemplo:
Entrada: Si no limpias los cristales, no ves nada y te frustras.
Salida: Si no se limpian los cristales, no se ve nada y uno se frustra.

Texto a corregir:
[TEXTO]
[/INST]
"""

PROMPT_FEEDBACK = """<s>[INST] <<SYS>>
Eres un tutor de español experto en redacción formal. Tu tarea es comparar un texto original con su versión corregida y explicar los cambios realizados.

LO QUE DEBES HACER:
- Explica brevemente si has corregido tildes, puntuación o faltas (solo si las había).
- CAMBIO DE PERSONA: Si has transformado un verbo en 2ª persona del singular (tú) a la forma con "se" en 3ª persona, explica por qué es mejor siguiendo esta teoría:
   - El uso de la 2ª persona (tú) es inadecuado en textos escritos y formales porque es demasiado coloquial y subjetivo. Además, interpela directamente al lector, rompe la objetividad y puede causar ambigüedad sobre a quién se refiere.
   - El "se" impersonal es preferible porque permite expresar generalidad sin señalar a nadie concreto. Mantiene un registro formal, es la opción recomendada en el español académico y aporta claridad y neutralidad.

REGLAS:
- No repitas el texto corregido.
- Da un feedback concreto, útil y orientado al aprendizaje.
- Si la frase original no presenta errores relevantes, indícalo explícitamente con un feedback neutro, señalando que el uso es correcto. 
- Usa un tono profesional pero fácil de entender.
<</SYS>>

Texto Original: [ORIGINAL]
Texto Corregido: [CORREGIDO]

Explicación técnica:
[/INST]"""


@torch.inference_mode()
def _generate_raw_prompt(prompt: str, max_new_tokens: int = 512) -> str:
    """Genera texto sin envolver en PROMPT_TEMPLATE (necesario para feedback)."""
    global _tokenizer, _model
    if not MODEL_LOADED or _tokenizer is None or _model is None:
        return ""

    inputs = _tokenizer(
        prompt,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=4096,
    )

    if hasattr(_model, "device"):
        inputs = {k: v.to(_model.device) for k, v in inputs.items()}

    output_ids = _model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=0.0,
        eos_token_id=_tokenizer.eos_token_id,
        pad_token_id=_tokenizer.pad_token_id,
    )

    generated = output_ids[0][inputs["input_ids"].shape[-1]:]
    return _tokenizer.decode(generated, skip_special_tokens=True).strip()


def generate_feedback(original: str, corrected: str) -> str:
    if not MODEL_LOADED:
        return ""

    prompt = (
        PROMPT_FEEDBACK
        .replace("[ORIGINAL]", original.strip())
        .replace("[CORREGIDO]", corrected.strip())
    )

    return _generate_raw_prompt(prompt, max_new_tokens=300)


def _set(progress: int, message: str):
    global LOAD_PROGRESS, LOAD_MESSAGE
    with _lock:
        LOAD_PROGRESS = max(0, min(100, int(progress)))
        LOAD_MESSAGE = message


def _load_impl():
    global MODEL_LOADED, _tokenizer, _model
    MODEL_LOADED = False

    try:
        _set(5, "Inicializando carga…")
        try:
            compute_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float16
        except Exception:
            compute_dtype = torch.float16

        _set(20, "Preparando configuración de cuantización NF4…")
        nf4_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
        )

        _set(40, "Cargando tokenizer…")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True)
        if _tokenizer.pad_token is None:
            _tokenizer.pad_token = _tokenizer.eos_token

        _set(75, "Cargando modelo (esto puede tardar)…")
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            quantization_config=nf4_config,
            device_map="auto",
        )

        _model.eval()

        _set(95, "Finalizando…")
        time.sleep(0.5)
        MODEL_LOADED = True
        _set(100, "✅ Modelo cargado y listo")
    except Exception as e:
        _set(0, f"❌ Error cargando modelo: {e}")
        MODEL_LOADED = False


def ensure_model_loaded(async_load: bool = True):
    global _thread, MODEL_LOADED
    if MODEL_LOADED and _model is not None and _tokenizer is not None:
        return
    if _thread and _thread.is_alive():
        return
    if async_load:
        _thread = threading.Thread(target=_load_impl, daemon=True)
        _thread.start()
    else:
        _load_impl()


def _format_prompt(document_text: str) -> str:
    return PROMPT_TEMPLATE.replace("[TEXTO]", document_text.strip())


@torch.inference_mode()
def _generate_once(text: str, max_new_tokens: int = 512) -> str:
    global _tokenizer, _model
    if not MODEL_LOADED or _tokenizer is None or _model is None:
        raise RuntimeError("El modelo aún no está cargado.")

    prompt = _format_prompt(text)
    inputs = _tokenizer(
        prompt,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=4096,
    )

    if hasattr(_model, "device"):
        inputs = {k: v.to(_model.device) for k, v in inputs.items()}

    output_ids = _model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=0.0,
        eos_token_id=_tokenizer.eos_token_id,
        pad_token_id=_tokenizer.pad_token_id,
    )

    generated = output_ids[0][inputs["input_ids"].shape[-1]:]
    text_out = _tokenizer.decode(generated, skip_special_tokens=True)
    return text_out.strip()

def correct_text(sentences: List[str], batch_size: int = 4, max_new_tokens: int = 512) -> List[str]:
    document = " ".join(s.strip() for s in sentences if isinstance(s, str) and s.strip())
    if not document:
        return [""]
    corrected = _generate_once(document, max_new_tokens=max_new_tokens)
    return [corrected]

def correct_full_text(text: str) -> str:
    if not text:
        return ""
    return _generate_once(text)