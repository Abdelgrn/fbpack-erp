"""Lecture de la fiche BAT par l'API Gemini (même API que « Scan Étiquette (IA) » du stock).

- Clé : variable d'environnement GEMINI_API_KEY. Jamais écrite dans le code ni dans l'URL :
  elle part dans l'en-tête x-goog-api-key.
- Modèle : variable GEMINI_MODEL, sinon gemini-3.8-flash (stable). Le modèle gemini-1.5-flash
  utilisé jusqu'ici est retiré depuis le 29/09/2025 (réponse 404).
- Appel HTTP avec urllib (aucun paquet ajouté). Les messages d'erreur ne contiennent jamais la clé.
- La réponse est une proposition : la validation humaine reste obligatoire avant enregistrement.
"""
import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request

from PIL import Image

DEFAULT_MODEL = 'gemini-3.8-flash'
API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
TIMEOUT_S = 60
# V1.12 : erreurs passagères (surcharge 503, 429, 5xx, délai) -> nouvel essai, puis modèle de secours.
MODEL_FALLBACKS = ['gemini-3.5-flash-lite', 'gemini-3.6-flash']
TRANSIENT_HTTP = {429, 500, 502, 503, 504}
# V1.13 : surcharge 503 souvent passagère -> attentes croissantes ; budget total borné (sous Gunicorn 240 s).
RETRY_WAITS_S = [4, 10]
TOTAL_BUDGET_S = 100      # V1.14 : 100 s max pour l'opérateur (au lieu de plus de 4 min)

PROMPT = """Tu lis une fiche BAT d'impression flexo (couscous, chips…). Réponds UNIQUEMENT par un objet JSON
de la forme :
{"nom_job": string|null, "laize_piste_mm": number|null, "laize_totale_mm": number|null,
 "pas_coupe_mm": number|null, "poses_en_laize": integer|null, "poses_en_coupe": integer|null,
 "lpi": number|null, "nombre_couleurs_annonce": integer|null, "fournisseur_cliches": string|null,
 "encres": [{"nom": string|null, "cm2": number|null, "pourcent": number|null}]}

Règles :
- "encres" : uniquement les colonnes du tableau de légende (pastilles avec nom, cm² et %), une entrée
  par colonne, dans l'ordre de gauche à droite. N'ajoute AUCUNE couleur de l'illustration (maquette).
- "nom" : le nom exactement tel qu'imprimé sous la pastille. Si illisible, mets null. N'invente jamais
  un nom d'après la position (ne déduis pas « Cyan » ou « Black » d'un rang).
- "cm2" et "pourcent" : les valeurs imprimées sous chaque pastille ; null si illisibles.
- nom_job : le texte après « JOB: » tel qu'imprimé.
- laize_piste_mm : après « LAIZE: ». laize_totale_mm : après « LAIZE Totale ».
- pas_coupe_mm : après « PAS DE COUPE ». lpi : après « LINIÉATURE » (valeur en LPI).
- poses_en_laize / poses_en_coupe : après « NBR .POSES EN LAIZE » / « NBR .POSES EN COUPE ».
- nombre_couleurs_annonce : après « Nbr de couleurs ».
- fournisseur_cliches : le nom du fournisseur de clichés imprimé sur la fiche (logo ou texte, par
  exemple « STUDIO FLEXO », « POLY SLIM », « YAHIAOUI PHOTOGRAVURE ») ; null si absent. N'invente pas.
- Mets null pour toute valeur que tu ne vois pas. Pas de texte hors du JSON."""


class VisionError(Exception):
    """Erreur IA avec un message sûr (sans clé ni contenu de requête)."""


def api_configured():
    return bool(os.environ.get('GEMINI_API_KEY', '').strip())


def _model():
    return os.environ.get('GEMINI_MODEL', '').strip() or DEFAULT_MODEL


def image_to_jpeg_b64(im, max_w=2048):
    """Image -> JPEG base64 (réduite à max_w de large si besoin)."""
    im = im.convert('RGB')
    if im.width > max_w:
        im = im.resize((max_w, int(round(im.height * max_w / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode('ascii')


def build_payload(b64_jpeg):
    return {
        'contents': [{'parts': [
            {'text': PROMPT},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_jpeg}},
        ]}],
        'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'},
    }


def call_gemini(payload, timeout=TIMEOUT_S):
    """Envoie la requête ; retourne le texte renvoyé par le modèle.

    V1.14 : chaque modèle de la chaîne (principal puis secours) = 2 essais sur erreur passagère
    (429/5xx), attente 4 s entre eux. Chaîne : gemini-3.8-flash -> gemini-3.5-flash-lite -> gemini-3.6-flash.
    2 échecs réseau au total maximum. Budget total borné à TOTAL_BUDGET_S (100 s).
    Une erreur permanente (400, 401, 403, 404) n'est pas relancée.
    Le message d'erreur final ne contient jamais la clé.
    """
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise VisionError('clé GEMINI_API_KEY absente')
    start = time.monotonic()
    primary = _model()
    models = [primary] + [m for m in MODEL_FALLBACKS if m != primary]
    last = 'réseau indisponible ou délai dépassé'
    network_failures = 0
    for model in models:
        attempts = 2
        for n in range(attempts):
            left = TOTAL_BUDGET_S - (time.monotonic() - start)
            if left <= 5:
                raise VisionError(f'{last} (délai total dépassé)')
            req = urllib.request.Request(
                API_URL.format(model=model),
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'x-goog-api-key': key},
                method='POST')
            try:
                with urllib.request.urlopen(req, timeout=min(timeout, left)) as resp:
                    body = json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as exc:
                last = f'erreur HTTP {exc.code} de l’API'
                if exc.code not in TRANSIENT_HTTP:
                    raise VisionError(last) from None
                if n + 1 < attempts:
                    wait = RETRY_WAITS_S[min(n, len(RETRY_WAITS_S) - 1)]
                    if wait < TOTAL_BUDGET_S - (time.monotonic() - start):
                        time.sleep(wait)
                        continue
                break          # essais épuisés pour ce modèle : modèle de secours
            except (urllib.error.URLError, TimeoutError, OSError):
                last = 'réseau indisponible ou délai dépassé'
                network_failures += 1
                if network_failures >= 2:
                    raise VisionError(f'{last} après plusieurs essais') from None
                continue
            except ValueError:
                raise VisionError('réponse API illisible') from None
            try:
                return body['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError, TypeError):
                raise VisionError('réponse IA vide (contenu peut-être bloqué)') from None
    raise VisionError(f'{last} après plusieurs essais')


def parse_json_text(text):
    cleaned = re.sub(r'```(?:json)?\s*|\s*```', '', text or '').strip()
    try:
        data = json.loads(cleaned)
    except ValueError:
        raise VisionError('réponse IA non JSON') from None
    if not isinstance(data, dict):
        raise VisionError('réponse IA inattendue')
    return data


def read_bat(im, max_w=2048):
    """Lit une image de fiche BAT ; retourne le dict JSON du modèle. Lève VisionError."""
    payload = build_payload(image_to_jpeg_b64(im, max_w=max_w))
    return parse_json_text(call_gemini(payload))
