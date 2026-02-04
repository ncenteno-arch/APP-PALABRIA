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
Eres un asistente experto en corrección de textos en español.

Tu única tarea es transformar los verbos en segunda persona del singular con valor impersonal a la forma impersonal con “se” + verbo en tercera persona.

REGLAS OBLIGATORIAS:
- Mantén el tiempo verbal original.
- Mantén la concordancia: si el elemento al que se refiere el verbo es plural, el verbo debe ir en plural (ej.: "si vendes manzanas" → "se venden manzanas").
- No cambies palabras, puntuación ni estructura sintáctica salvo lo estrictamente necesario para aplicar la transformación.
- No agregues explicaciones, comentarios ni contenido adicional.
- Mantén un registro formal, académico o científico.

<</SYS>>

Ejemplos:
1. Tú explicas cómo funciona el sistema.
Se explica cómo funciona el sistema.
2. Cuando comes mucho, te duele el estómago.
Cuando se come mucho, duele el estómago.
3. En la investigación científica, si tú interpretas incorrectamente los resultados, puedes generar grandes incongruencias.
En la investigación científica, si se interpretan incorrectamente los resultados, se pueden generar grandes incongruencias.
4. Cuando juegas un partido complicado, y aunque tengas experiencia, tú cometes errores que afectan al resultado final.
Cuando se juega un partido complicado, y aunque se tenga experiencia, se cometen errores que afectan al resultado final.
5. ¿Puedes fumar?
¿Se puede fumar?
6. Si vendes manzanas, obtienes beneficios.
Si se venden manzanas, se obtienen beneficios.

Texto a corregir:
[TEXTO]
[/INST]
"""


PROMPT_FEEDBACK = """<s>[INST] <<SYS>>
Eres un tutor de español que ayuda a mejorar la redacción académica.

Tu tarea es explicar de forma sencilla los cambios realizados entre un texto original y su versión corregida.

Explica únicamente los cambios que realmente aparecen en el texto corregido.
No menciones errores que no se hayan corregido.
No inventes errores.
No uses listas ni enumeraciones.
Redacta el feedback en uno o dos párrafos breves y claros.

Si se ha cambiado el uso de "tú", explica que en textos escritos y académicos no se habla directamente al lector.
El uso del "tú" impersonal es más propio del lenguaje oral o divulgativo y puede hacer que el texto
suene subjetivo o demasiado cercano.
La forma impersonal con "se" permite expresar las ideas de manera más general, objetiva y adecuada
para este tipo de textos.

Si se ha cambiado la forma del verbo, explica que se ha hecho para que la frase sea correcta y natural en español.
Si no hay otros errores importantes, indícalo claramente.

Mantén un tono claro, directo, profesional y pedagógico.
<</SYS>>

Texto original: [ORIGINAL]
Texto corregido: [CORREGIDO]

Explicación:
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
