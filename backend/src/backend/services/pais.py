from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.pais import Pais

# Catálogo de referencia: no lleva restricción de rol adicional, basta con un
# rol válido en la petición. Lo consume el selector de país del formulario de
# aliados.


def listar_paises(db: Session) -> Sequence[Pais]:
    return db.scalars(select(Pais).order_by(Pais.nombre)).all()
