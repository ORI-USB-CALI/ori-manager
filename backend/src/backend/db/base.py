from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Importar modelos para registro en metadata
from backend.models import Aliado, Convenio  # noqa: F401


