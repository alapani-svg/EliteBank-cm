import cloudinary
import cloudinary.uploader
from django.conf import settings

cloudinary.config(
    cloud_name = settings.CLOUDINARY_CLOUD_NAME,
    api_key    = settings.CLOUDINARY_API_KEY,
    api_secret = settings.CLOUDINARY_API_SECRET,
    secure     = True
)


def upload_avatar(file, user_id: str) -> str:
    """
    Uploads a profile picture to Cloudinary.
    Overwrites the previous avatar for the same user.
    Returns the secure URL string.
    """
    result = cloudinary.uploader.upload(
        file,
        folder        = "elite_bank/avatars",
        public_id     = f"avatar_{user_id}",
        resource_type = "image",
        overwrite     = True,
        transformation = [
            {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
            {"quality": "auto", "fetch_format": "auto"}
        ]
    )
    return result["secure_url"]