"""
Image Persistence Port - Outbound Port
"""
from abc import ABC, abstractmethod


class ImagePersistencePort(ABC):

    @abstractmethod
    def save_image(self, path: str, data: bytes) -> str: ...

    @abstractmethod
    def get_image(self, path: str) -> bytes: ...
