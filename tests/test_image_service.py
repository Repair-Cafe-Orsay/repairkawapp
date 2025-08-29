from io import BytesIO

from PIL import Image

from repairkawapp.services.image_service import MAX_PHOTO_BYTES, process_user_photo


def make_image_bytes(color=(123, 45, 67), size=(800, 600)):
    img = Image.new("RGB", size, color)
    bio = BytesIO()
    img.save(bio, format="PNG")  # PNG pour petite taille
    return bio.getvalue()


def test_process_valid_image(tmp_path):
    raw = make_image_bytes()
    fn, err = process_user_photo(
        raw,
        str(tmp_path),
        user_id=42,
        form_get=lambda k, d=None: {
            "crop_x": "10",
            "crop_y": "15",
            "crop_w": "200",
            "crop_h": "150",
        }.get(k, d),
    )
    assert err is None
    assert fn and fn.startswith("user_42_")
    out_path = tmp_path / fn
    assert out_path.exists()
    with Image.open(out_path) as im:
        assert im.size == (400, 400)  # redimension standard


def test_process_too_large_size(tmp_path):
    # Génère un blob > MAX_PHOTO_BYTES (contenu arbitraire)
    raw = b"0" * (MAX_PHOTO_BYTES + 10)
    fn, err = process_user_photo(raw, str(tmp_path), 7, lambda *_: None)
    assert fn is None
    assert err and "trop volumineux" in err.lower()


def test_process_invalid_image_bytes(tmp_path):
    # Taille OK mais données non image
    raw = b"not-an-image"
    fn, err = process_user_photo(raw, str(tmp_path), 99, lambda *_: None)
    assert fn is None
    assert err and "erreur" in err.lower()


def test_process_invalid_crop_fallback_center(tmp_path):
    raw = make_image_bytes(size=(1000, 500))

    # Crop volontairement invalide (w/h out of range)
    def form_get(key, default=None):
        data = {
            "crop_x": "0",
            "crop_y": "0",
            "crop_w": "99999",
            "crop_h": "99999",
        }
        return data.get(key, default)

    fn, err = process_user_photo(raw, str(tmp_path), 5, form_get)
    assert err is None
    assert fn
    out_path = tmp_path / fn
    with Image.open(out_path) as im:
        assert im.size == (400, 400)
