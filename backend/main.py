# backend/main.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import time

import backend.model as model
from backend.metrics import _normalize_for_diff, word_levenshtein_count
from backend.utils import extract_text_from_pdf, split_into_sentences, posible_tu_impersonal
from backend.db import (
    init_db, user_exists, create_user, get_user_id,
    record_usage, create_document, insert_metric,
    get_user_overview, get_user_documents, get_document_metrics,
    sanitize_username, delete_document, record_login_ts,
    close_open_session, get_user_weekly_activity
)

app = FastAPI(title="PALABRIA Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.get("/status/")
def check_status():
    return {
        "modelo_listo": model.MODEL_LOADED,
        "progress": model.LOAD_PROGRESS,
        "message": model.LOAD_MESSAGE,
    }

@app.post("/load/")
def trigger_load():
    model.ensure_model_loaded(async_load=True)
    return {"ok": True}

@app.post("/users/create")
def user_create(username: str = Form(...)):
    try:
        username = sanitize_username(username)
        if user_exists(username):
            raise HTTPException(status_code=409, detail="El usuario ya existe. Elige otro nombre.")
        uid = create_user(username)
        record_usage(uid, "login", None)
        record_login_ts(uid, time.time())
        return {"ok": True, "user_id": uid, "username": username}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/users/login")
def user_login(username: str = Form(...)):
    try:
        username = sanitize_username(username)
        uid = get_user_id(username)
        if uid is None:
            raise HTTPException(status_code=404, detail="La cuenta no existe. Crea una nueva.")
        record_usage(uid, "login", None)
        record_login_ts(uid, time.time())
        return {"ok": True, "user_id": uid, "username": username}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/users/logout")
def user_logout(username: str = Form(...)):
    try:
        username = sanitize_username(username)
        uid = get_user_id(username)
        if uid is None:
            raise HTTPException(status_code=404, detail="Usuario no válido.")
        close_open_session(uid, time.time())
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/users/heartbeat")
def user_heartbeat(username: str = Form(...)):
    try:
        username = sanitize_username(username)
        uid = get_user_id(username)
        if uid is None:
            raise HTTPException(status_code=404, detail="Usuario no válido.")
        now = time.time()
        record_usage(uid, "heartbeat", now)
        close_open_session(uid, now_epoch=now, idle_secs=1800)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/process/")
async def process_pdf(
    file: UploadFile = File(...),
    username: str = Form(...),
):
    username = sanitize_username(username)
    uid = get_user_id(username)
    if uid is None:
        raise HTTPException(status_code=403, detail="Usuario no válido. Inicia sesión con una cuenta existente.")

    content = await file.read()
    original_text = extract_text_from_pdf(content)

    errores_posibles, _ = posible_tu_impersonal(original_text)
    if not isinstance(errores_posibles, list):
        errores_posibles = []

    corrected_text = model.correct_full_text(original_text)
    feedback = model.generate_feedback(original_text, corrected_text)

    sentences = split_into_sentences(original_text)
    total_frases = len(sentences)
    total_errores = len(errores_posibles)
    cambios_modelo_total = word_levenshtein_count(original_text, corrected_text)

    text_hash = hashlib.sha256((original_text or "").encode("utf-8")).hexdigest()
    doc_id = create_document(uid, file.filename, text_hash)

    insert_metric(doc_id, "total_frases", float(total_frases))
    insert_metric(doc_id, "frases_con_tu_impersonal", float(total_errores))
    insert_metric(doc_id, "cambios_propuestos_modelo", float(cambios_modelo_total))
    insert_metric(doc_id, "cambios_realizados_usuario", float(cambios_modelo_total))

    record_usage(uid, "pdf_uploaded", None)

    return {
        "doc_id": doc_id,
        "original_text": original_text,
        "corrected": corrected_text,
        "feedback": feedback,
        "errores_posibles": errores_posibles,
        "mensaje_errores": (
            "No se detectaron errores de 'tú' impersonal."
            if not errores_posibles
            else f"Se detectaron {len(errores_posibles)} posibles usos del 'tú' impersonal."
        ),
        "metricas": {
            "total_frases": total_frases,
            "frases_con_tu_impersonal": total_errores,
            "cambios_propuestos_modelo": cambios_modelo_total,
            "cambios_realizados_usuario": cambios_modelo_total,
        },
    }

@app.post("/process_text/")
async def process_text(
    username: str = Form(...),
    text: str = Form(...),
    filename: str = Form(None),
):
    username = sanitize_username(username)
    uid = get_user_id(username)
    if uid is None:
        raise HTTPException(status_code=403, detail="Usuario no válido. Inicia sesión con una cuenta existente.")

    original_text = text or ""

    errores_posibles, _ = posible_tu_impersonal(original_text)
    if not isinstance(errores_posibles, list):
        errores_posibles = []

    corrected_text = model.correct_full_text(original_text)
    feedback = model.generate_feedback(original_text, corrected_text)

    sentences = split_into_sentences(original_text)
    total_frases = len(sentences)
    total_errores = len(errores_posibles)
    cambios_modelo_total = word_levenshtein_count(original_text, corrected_text)

    text_hash = hashlib.sha256((original_text or "").encode("utf-8")).hexdigest()
    doc_id = create_document(uid, filename or "entrada_texto.txt", text_hash)

    insert_metric(doc_id, "total_frases", float(total_frases))
    insert_metric(doc_id, "frases_con_tu_impersonal", float(total_errores))
    insert_metric(doc_id, "cambios_propuestos_modelo", float(cambios_modelo_total))
    insert_metric(doc_id, "cambios_realizados_usuario", float(cambios_modelo_total))

    record_usage(uid, "text_uploaded", None)

    return {
        "doc_id": doc_id,
        "original_text": original_text,
        "corrected": corrected_text,
        "feedback": feedback,
        "errores_posibles": errores_posibles,
        "mensaje_errores": (
            "No se detectaron errores de 'tú' impersonal."
            if not errores_posibles
            else f"Se detectaron {len(errores_posibles)} posibles usos del 'tú' impersonal."
        ),
        "metricas": {
            "total_frases": total_frases,
            "frases_con_tu_impersonal": total_errores,
            "cambios_propuestos_modelo": cambios_modelo_total,
            "cambios_realizados_usuario": cambios_modelo_total,
        },
    }

@app.post("/documents/{doc_id}/metrics")
def add_document_metric(
    doc_id: int,
    name: str = Form(...),
    value: float = Form(...),
):
    try:
        insert_metric(doc_id, name, float(value))
        return {"ok": True, "document_id": doc_id, "metric_name": name, "metric_value": float(value)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/documents/{doc_id}/user_changes")
def update_user_changes(
    doc_id: int,
    changes: int = Form(...),
):
    try:
        insert_metric(doc_id, "cambios_realizados_usuario", float(changes))
        return {"ok": True, "document_id": doc_id, "metric_name": "cambios_realizados_usuario", "metric_value": float(changes)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/users/{username}/overview")
def user_overview(username: str):
    return get_user_overview(username)

@app.get("/users/{username}/documents")
def user_documents(username: str):
    return {"documents": get_user_documents(username)}

@app.get("/documents/{doc_id}/metrics")
def document_metrics(doc_id: int):
    return {"doc_id": doc_id, "metrics": get_document_metrics(doc_id)}

@app.get("/users/{username}/weekly_activity")
def user_weekly_activity(username: str):
    return {"username": username, "activity": get_user_weekly_activity(username)}

@app.delete("/documents/{doc_id}")
def delete_doc(doc_id: int):
    ok = delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return {"ok": True, "deleted_id": doc_id}