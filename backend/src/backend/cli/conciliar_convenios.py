"""python -m backend.cli.conciliar_convenios [--simular] [--fecha-referencia AAAA-MM-DD]."""

import argparse
import logging
from datetime import date
from time import sleep

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from backend.core.config import settings
from backend.db.session import SessionLocal
from backend.services.ciclo_vida_convenios import conciliar_estados
from backend.services.renovaciones import fecha_actual_dominio

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Conciliar estados de convenios (America/Bogota)"
    )
    parser.add_argument("--fecha-referencia", type=date.fromisoformat)
    parser.add_argument(
        "--simular", action="store_true", help="Mostrar cambios sin persistirlos"
    )
    parser.add_argument("--intentos", type=int, choices=range(1, 4), default=3)
    args = parser.parse_args(argv)
    if (
        args.fecha_referencia is not None
        and not args.simular
        and settings.app_env not in {"development", "test"}
    ):
        parser.error(
            "Las ejecuciones reales con --fecha-referencia solo están permitidas "
            "en development o test. En otros entornos utiliza --simular o elimina "
            "--fecha-referencia para usar la fecha actual de America/Bogota."
        )
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    referencia = args.fecha_referencia or fecha_actual_dominio()
    for intento in range(1, args.intentos + 1):
        try:
            with SessionLocal() as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                db.execute(text("SET LOCAL statement_timeout = '120s'"))
                resultado = conciliar_estados(db, referencia, simular=args.simular)
            logger.info(
                "conciliacion_completa referencia=%s intento=%s cambios=%s sin_fecha=%s legado_inconsistente=%s simulado=%s",
                referencia,
                intento,
                len(resultado.cambios),
                len(resultado.sin_fecha),
                len(resultado.legado_inconsistente),
                resultado.simulado,
            )
            return 0
        except (SQLAlchemyError, OSError) as exc:
            sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
            transitorio = isinstance(exc, DBAPIError) and (
                exc.connection_invalidated
                or sqlstate in {"40001", "40P01", "55P03", "57P03"}
                or (sqlstate is not None and sqlstate.startswith("08"))
                or (isinstance(exc, OperationalError) and sqlstate is None)
            )
            # No imprimir conexiones, contraseñas ni parámetros SQL en logs.
            logger.error(
                "conciliacion_fallida intento=%s error=%s sqlstate=%s",
                intento,
                type(exc).__name__,
                sqlstate,
            )
            if not transitorio or intento == args.intentos:
                return 1
            sleep(2**intento)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
