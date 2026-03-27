"""
Domain Exceptions
"""


class DomainException(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)


class EntityNotFoundException(DomainException):
    def __init__(self, entity: str, entity_id: int):
        super().__init__(detail=f"{entity} com ID {entity_id} não encontrado", status_code=404)


class DuplicateEntityException(DomainException):
    def __init__(self, entity: str, field: str, value: str):
        super().__init__(detail=f"{entity} com {field} '{value}' já existe", status_code=409)


class InvalidEntityException(DomainException):
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=422)


class ConcurrencyConflictException(DomainException):
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=409)


class ScrapingException(DomainException):
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=500)


class PublishException(DomainException):
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=502)
