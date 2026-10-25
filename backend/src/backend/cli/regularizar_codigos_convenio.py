"""python -m backend.cli.regularizar_codigos_convenio [--simular] [--anio-politica AAAA] [--autorizado-por ID].

Procedimiento autorizado de HT-06 CA-08: asigna el código institucional a los
convenios ya formalizados que quedaron sin él, de antes de que la formalización
lo generara sola.

La ejecución real está restringida a `development` y `test`. Aplicarla sobre
Staging o Producción requiere la validación institucional de la política de año
y una autorización explícita que todavía no existe.
"""

import argparse
import logging
from time import sleep

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from backend.core.config import settings
from backend.core.roles import CodigoRol
from backend.db.session import SessionLocal
from backend.models.usuario import Usuario
from backend.services.regularizacion_codigos import regularizar_codigos

logger = logging.getLogger(__name__)

ENTORNOS_PERMITIDOS = {"development", "test"}


def _anio(valor: str) -> int:
    anio = int(valor)
    if not 1900 <= anio <= 2999:
        raise argparse.ArgumentTypeError("El año debe tener cuatro dígitos")
    return anio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regularizar el código institucional de convenios formalizados "
            "(America/Bogota)"
        )
    )
    parser.add_argument(
        "--simular",
        action="store_true",
        help="Mostrar los códigos que se asignarían sin persistirlos",
    )
    parser.add_argument(
        "--anio-politica",
        type=_anio,
        help=(
            "Forzar el año de todos los códigos. Sin este argumento se usa el "
            "año real de formalización de cada convenio."
        ),
    )
    parser.add_argument(
        "--autorizado-por",
        type=int,
        help=(
            "Id del usuario ADMINISTRADOR_ORI que autoriza la ejecución. Queda "
            "registrado como originador de una ejecución automática."
        ),
    )
    parser.add_argument("--intentos", type=int, choices=range(1, 4), default=3)
    args = parser.parse_args(argv)
    if not args.simular and settings.app_env not in ENTORNOS_PERMITIDOS:
        parser.error(
            "Las ejecuciones reales solo están permitidas en development o test. "
            "La regularización sobre datos reales exige la validación "
            "institucional de la política de año; utiliza --simular."
        )
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    for intento in range(1, args.intentos + 1):
        try:
            with SessionLocal() as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                db.execute(text("SET LOCAL statement_timeout = '120s'"))
                originador = _originador(db, args.autorizado_por, parser)
                resultado = regularizar_codigos(
                    db,
                    anio_politica=args.anio_politica,
                    originador=originador,
                    simular=args.simular,
                )
            logger.info(
                "regularizacion_completa intento=%s asignados=%s "
                "sin_fecha_confiable=%s anio_politica=%s simulado=%s",
                intento,
                len(resultado.asignados),
                len(resultado.sin_fecha_confiable),
                args.anio_politica,
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
                "regularizacion_fallida intento=%s error=%s sqlstate=%s",
                intento,
                type(exc).__name__,
                sqlstate,
            )
            if not transitorio or intento == args.intentos:
                return 1
            sleep(2**intento)
    return 1


def _originador(
    db, usuario_id: int | None, parser: argparse.ArgumentParser
) -> Usuario | None:
    """Usuario que autoriza la ejecución, si se indicó.

    Debe existir y ser ADMINISTRADOR_ORI: no se acepta cualquier id ni se
    sustituye por una cuenta ficticia cuando no se indica ninguno (RN-07 de
    HT-09). Sin el argumento la ejecución queda como automática sin originador.
    """
    if usuario_id is None:
        return None
    usuario = db.scalar(select(Usuario).where(Usuario.id == usuario_id))
    if usuario is None:
        parser.error(f"No existe el usuario {usuario_id}")
    if usuario.rol.codigo != CodigoRol.ADMINISTRADOR_ORI.value:
        parser.error(
            "La regularización solo puede autorizarla un ADMINISTRADOR_ORI"
        )
    return usuario


if __name__ == "__main__":
    raise SystemExit(main())
