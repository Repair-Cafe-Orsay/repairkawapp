"""Service utilitaire pour traitement des photos de profil.

Centralise la logique: taille max, recadrage carré (option coordonnées), redimensionnement 400x400,
conversion JPEG. Retourne (filename, error_message).
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import Optional, Tuple
import os
from PIL import Image

MAX_PHOTO_BYTES = 3 * 1024 * 1024  # 3 Mo

def process_user_photo(raw_bytes: bytes, upload_folder: str, user_id: int,
                       form_get) -> Tuple[Optional[str], Optional[str]]:
    """Traite une photo brute et retourne (nom_fichier, erreur).

    form_get: fonction comme request.form.get
    Coordonnées de recadrage attendues: crop_x, crop_y, crop_w, crop_h
    Si absentes/invalides => recadrage carré centré.
    """
    if len(raw_bytes) > MAX_PHOTO_BYTES:
        return None, f"Fichier trop volumineux (> {MAX_PHOTO_BYTES//1024} Ko)."
    try:
        img = Image.open(BytesIO(raw_bytes))
        img = img.convert('RGBA') if img.mode in ('P','LA') else img.convert('RGB')
        try:
            x = int(float(form_get('crop_x', 0)))
            y = int(float(form_get('crop_y', 0)))
            w = int(float(form_get('crop_w', 0)))
            h = int(float(form_get('crop_h', 0)))
        except (TypeError, ValueError):
            x = y = 0; w = h = 0
        W, H = img.size
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > W or y+h > H:
            side = min(W, H)
            x = (W - side)//2
            y = (H - side)//2
            w = h = side
        img = img.crop((x, y, x + w, y + h))
        img = img.resize((400, 400), Image.LANCZOS)
        filename = f"user_{user_id}_{int(datetime.now().timestamp())}.jpg"
        path = os.path.join(upload_folder, filename)
        img.save(path, format='JPEG', quality=88)
        return filename, None
    except Exception:
        return None, "Erreur lors du traitement de l'image (format non supporté?)."
