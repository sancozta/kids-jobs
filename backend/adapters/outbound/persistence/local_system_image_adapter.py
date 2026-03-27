"""
Local System Image Adapter - Outbound Adapter
"""
import os

from application.domain.exceptions.domain_exceptions import DomainException
from application.ports.outbound.persistence.image_persistence_port import ImagePersistencePort


class LocalSystemImageAdapter(ImagePersistencePort):

    def __init__(self, base_path: str = "data/images"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def save_image(self, path: str, data: bytes) -> str:
        full_path = os.path.join(self.base_path, path)
        directory = os.path.dirname(full_path)
        os.makedirs(directory, exist_ok=True)

        try:
            with open(full_path, "wb") as f:
                f.write(data)
            return full_path
        except Exception as e:
            raise DomainException(f"Failed to save image: {e}", status_code=500)

    def get_image(self, path: str) -> bytes:
        full_path = os.path.join(self.base_path, path)
        try:
            with open(full_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise DomainException("Image not found", status_code=404)
        except Exception as e:
            raise DomainException(f"Failed to read image: {e}", status_code=500)
