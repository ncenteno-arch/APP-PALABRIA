# # backend/utils.py
import pdfplumber
import io
import re
import spacy

nlp = spacy.load("es_core_news_lg")

def extract_text_from_pdf(pdf_bytes):
    pdf_file = io.BytesIO(pdf_bytes)
    with pdfplumber.open(pdf_file) as pdf:
        textos = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                textos.append(t)
        return "\n".join(textos)

def split_into_sentences(text):
    """Divide el texto en oraciones usando spaCy."""
    doc = nlp(text or "")
    return [s.text.strip() for s in doc.sents]
 
def es_verbo_segunda_persona(verbo):
    """
    Detecta 2ª persona REAL:
    - Verbos finitos con Person=2 (spaCy)
    - Infinitivos o gerundios con clítico -te (prepararte, corregirte, etc.)
    """

    # 1) Verbos FINITOS (reales)
    if "VerbForm=Fin" in verbo.morph:
        if verbo.morph.get("Person") == ["2"]:
            return True

    # 2) Infinitivos/gerundios con clítico -te
    texto = verbo.text.lower()
    if texto.endswith("te"):
        if verbo.morph.get("VerbForm") in (["Inf"], ["Ger"]):
            return True

    return False


def encontrar_verbos_segunda_persona(sent):
    """
    Encuentra verbos reales (VERB/AUX) en 2.ª persona.
    No se basa en terminaciones, solo spaCy + enclíticos.
    """
    verbos_reales = [t for t in sent if t.pos_ in ["VERB", "AUX"]]
    verbos_2p = [v for v in verbos_reales if es_verbo_segunda_persona(v)]
    return verbos_reales, verbos_2p

def posible_tu_impersonal(texto):
    """
    Evalúa exactamente las mismas oraciones que split_into_sentences().
    Marca las frases que contengan verbos en 2ª persona del singular.
    """
    sentences = split_into_sentences(texto or "")
    posibles = []

    for s in sentences:
        doc = nlp(s)
        _, verbos_2p = encontrar_verbos_segunda_persona(doc)

        if verbos_2p:
            posibles.append(s)

    mensaje = (
        "No se detectaron errores de 'tú' impersonal."
        if not posibles else
        f"Se detectaron {len(posibles)} posibles usos del 'tú' impersonal."
    )

    return posibles, mensaje