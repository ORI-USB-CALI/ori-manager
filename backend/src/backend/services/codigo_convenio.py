"""HT-06: generación del código institucional del convenio.

Vive en un módulo propio para que la formalización (`firmas`) y el
procedimiento de regularización compartan el mismo generador sin pasar por
`convenios`, que ya participa en otras cadenas de importación.

La nomenclatura `USB-ORI-AAAA-NNNNN` está aprobada por el PO (RN-03). El
código solo se asigna al formalizar un convenio (RN-01) y es responsabilidad
exclusiva del backend (RN-02).
"""

from sqlalchemy import Integer, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.models.convenio import Convenio

PREFIJO_INSTITUCIONAL = "USB-ORI"
DIGITOS_MINIMOS_CONSECUTIVO = 5


def formatear_codigo(anio: int, consecutivo: int) -> str:
    """Compone `USB-ORI-AAAA-NNNNN` (RN-03, RN-04, RN-06).

    Los cinco dígitos son un ancho mínimo, no un máximo: pasado 99999 el
    consecutivo ocupa los dígitos que necesite en lugar de truncarse o repetir
    un valor ya entregado (RN-12).
    """
    consecutivo_formateado = f"{consecutivo:0{DIGITOS_MINIMOS_CONSECUTIVO}d}"
    return f"{PREFIJO_INSTITUCIONAL}-{anio:04d}-{consecutivo_formateado}"


# Tope de dígitos al leer un consecutivo heredado: `ultimo_consecutivo` es
# entero de 32 bits, así que no se intenta convertir algo que no quepa. Un
# código con más dígitos no es un código institucional real.
_MAXIMO_DIGITOS_HEREDADOS = 9


def _consecutivo_ya_ocupado(anio: int):
    """Mayor consecutivo que ya ocupa un código institucional de ese año.

    El contador no puede nacer en cero: antes de que CA-05 cerrara el contrato
    de creación, HU-10 permitía teclear el código a mano. Si alguien escribió
    `USB-ORI-2026-00001`, un contador que arranque en cero generaría ese mismo
    código y la formalización chocaría contra el UNIQUE de `convenio.codigo`.

    Solo cuentan los códigos con la forma institucional exacta; uno cargado como
    `CONV-0001` no reserva ningún número.
    """
    prefijo = f"{PREFIJO_INSTITUCIONAL}-{anio:04d}-"
    return (
        select(
            func.coalesce(
                func.max(
                    func.substring(Convenio.codigo, len(prefijo) + 1).cast(Integer)
                ),
                0,
            )
        )
        .where(
            Convenio.codigo.op("~")(
                f"^{prefijo}[0-9]{{1,{_MAXIMO_DIGITOS_HEREDADOS}}}$"
            )
        )
        .scalar_subquery()
    )


def _incrementar(db: Session, anio: int) -> int | None:
    """Incrementa el contador del año en la base y devuelve el valor nuevo.

    Es un `UPDATE ... SET x = x + 1 RETURNING x`: la lectura, el incremento y
    la escritura ocurren en una sola instrucción, así que no hay ventana entre
    leer y escribir. El UPDATE toma el candado de fila por sí mismo, de modo
    que un competidor del mismo año espera a que esta transacción termine y
    entonces reevalúa sobre el valor ya confirmado.

    Se hace con el Core y no leyendo la entidad para incrementarla en Python:
    esa variante dependía de que la sesión hiciera `autoflush`, y la sesión de
    producción lo tiene desactivado. Dos llamadas en una misma transacción
    entregaban el mismo número.
    """
    return db.execute(
        update(ContadorCodigoConvenio)
        .where(ContadorCodigoConvenio.anio == anio)
        .values(ultimo_consecutivo=ContadorCodigoConvenio.ultimo_consecutivo + 1)
        .returning(ContadorCodigoConvenio.ultimo_consecutivo)
    ).scalar_one_or_none()


def siguiente_consecutivo(db: Session, anio: int) -> int:
    """Reserva el siguiente consecutivo del año y lo devuelve.

    Serializa a quienes compitan por el mismo año: el candado de la fila se
    mantiene hasta que termine la transacción que llama, así que conviene
    invocarla lo más tarde posible dentro de la operación. No se apoya en
    `MAX(codigo) + 1`, que bajo concurrencia entregaría el mismo valor dos
    veces (CA-03).

    Es correcta llamada varias veces en una misma transacción, como hace la
    regularización de convenios históricos.

    Si la transacción se revierte, el consecutivo vuelve a quedar libre: el
    contador no deja huecos por intentos fallidos.
    """
    consecutivo = _incrementar(db, anio)
    if consecutivo is None:
        # Dos transacciones pueden estrenar el mismo año a la vez. DO NOTHING
        # espera a que la otra confirme y entonces no inserta nada; el UPDATE
        # que sigue es el que ordena a ambas.
        # La fila del año nace sabiendo qué consecutivos ya ocupan códigos
        # heredados, para no generar uno que choque contra el UNIQUE.
        # Dos transacciones pueden estrenar el mismo año a la vez: DO NOTHING
        # espera a que la otra confirme y entonces no inserta nada; el UPDATE
        # que sigue es el que ordena a ambas.
        db.execute(
            insert(ContadorCodigoConvenio)
            .from_select(
                ["anio", "ultimo_consecutivo"],
                select(literal(anio), _consecutivo_ya_ocupado(anio)),
            )
            .on_conflict_do_nothing(index_elements=["anio"])
        )
        consecutivo = _incrementar(db, anio)
    if consecutivo is None:
        raise RuntimeError(
            f"No fue posible reservar el consecutivo del año {anio}"
        )
    return consecutivo


def asignar_codigo(db: Session, convenio: Convenio, anio: int) -> str:
    """Asigna el código del año indicado, o conserva el que el convenio ya tenga.

    Un convenio que ya tiene código no se reasigna nunca y tampoco consume un
    consecutivo: ni al cambiar de estado, ni al exportar, ni al repetir la
    regularización (CA-04, RN-08, RN-13).
    """
    if convenio.codigo is not None:
        return convenio.codigo
    convenio.codigo = formatear_codigo(anio, siguiente_consecutivo(db, anio))
    return convenio.codigo
