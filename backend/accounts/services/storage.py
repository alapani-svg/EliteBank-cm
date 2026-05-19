import cloudinary
import cloudinary.uploader
from django.conf import settings

cloudinary.config(
    cloud_name = settings.CLOUDINARY_CLOUD_NAME,
    api_key    = settings.CLOUDINARY_API_KEY,
    api_secret = settings.CLOUDINARY_API_SECRET,
    secure     = True
)


def upload_kyc_document(file, user_id: str, doc_type: str) -> dict:
    """
    Uploads a KYC document (CNI or Passport) to Cloudinary.
    Returns the secure URL and public_id.
    """
    result = cloudinary.uploader.upload(
        file,
        folder        = f"elite_bank/kyc/{user_id}",
        public_id     = f"{doc_type}_{user_id}",
        resource_type = "auto",
        overwrite     = True,
        tags          = ["kyc", doc_type, f"user_{user_id}"]
    )
    return {
        "url":       result["secure_url"],
        "public_id": result["public_id"],
        "format":    result["format"]
    }


def upload_avatar(file, user_id: str) -> str:
    """
    Uploads a profile picture to Cloudinary.
    Accepts all image formats (jpg, png, gif, webp, bmp, tiff, heic, svg, ico).
    Overwrites the previous avatar for the same user.
    Returns the secure URL string.
    """
    result = cloudinary.uploader.upload(
        file,
        folder           = "elite_bank/avatars",
        public_id        = f"avatar_{user_id}",
        resource_type    = "image",
        overwrite        = True,
        allowed_formats  = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "svg", "ico", "heic"],  # ← added
        transformation   = [
            {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
            {"quality": "auto", "fetch_format": "auto"}
        ]
    )
    return result["secure_url"]