"""HT-06 CA-08: regularización de convenios históricos sin código.

Nivel servicio. El control de argumentos y entorno del procedimiento se cubre
en test_cli_regularizar_codigos.py.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol
from backend.models.auditoria import Auditoria
from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.models.convenio import Convenio
from backend.models.enums import EjecucionAuditoria, EstadoConvenio
from backend.services.regularizacion_codigos import (
    anio_de_formalizacion,
    regularizar_codigos,
)
from backend.services.vigencia import ZONA_HORARIA_DOMINIO

# Años propios: el consecutivo es global y otras pruebas confirman de verdad.
ANIO = 2095
OTRO_ANIO = 2094


def _formalizado(db: Session, convenio: Convenio, *, activado: datetime | None):
    """Deja el convenio como formalizado sin código.

    `filtro_convenio_formalizado()` exige `fecha_firma` y un estado distinto de
    EN_TRAMITE/CANCELADO; `activado_en` es la marca verificable que decide el año.
    """
    convenio.estado = EstadoConvenio.VIGENTE.value
    convenio.fecha_firma = date(2020, 1, 1)
    convenio.activado_en = activado
    convenio.codigo = None
    db.commit()
    return convenio


def _en(anio: int, mes: int, dia: int) -> datetime:
    return datetime(anio, mes, dia, 12, 0, tzinfo=ZONA_HORARIA_DOMINIO)


def _codigos(db: Session, *convenios: Convenio) -> list[str | None]:
    db.expire_all()
    return [db.get(Convenio, c.id).codigo for c in convenios]


# --- Política de año ------------------------------------------------------


def test_el_anio_sale_de_la_marca_de_activacion(db: Session, gestor, crear_convenio):
    convenio = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 3, 10))

    assert anio_de_formalizacion(convenio) == ANIO


def test_sin_marca_verificable_no_hay_anio(db: Session, gestor, crear_convenio):
    # Tiene fecha_firma (la exige el filtro de formalizado) pero ninguna marca
    # que solo escriba formalizar(): no se deduce un año de un dato tecleable.
    convenio = _formalizado(db, crear_convenio(gestor), activado=None)

    assert anio_de_formalizacion(convenio) is None


def test_ca08_asigna_en_orden_cronologico_de_formalizacion(
    db: Session, gestor, crear_convenio
):
    # Se crean en orden inverso al de formalización para que el resultado no
    # pueda salir del orden de los ids.
    tardio = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 11, 2))
    temprano = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 3, 10))

    resultado = regularizar_codigos(db)

    assert _codigos(db, temprano, tardio) == [
        f"USB-ORI-{ANIO}-00001",
        f"USB-ORI-{ANIO}-00002",
    ]
    assert resultado.sin_fecha_confiable == ()


def test_ca08_cada_anio_lleva_su_propia_serie(db: Session, gestor, crear_convenio):
    uno = _formalizado(db, crear_convenio(gestor), activado=_en(OTRO_ANIO, 5, 1))
    dos = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 5, 1))

    regularizar_codigos(db)

    assert _codigos(db, uno, dos) == [
        f"USB-ORI-{OTRO_ANIO}-00001",
        f"USB-ORI-{ANIO}-00001",
    ]


def test_ca08_los_convenios_sin_fecha_verificable_se_reportan(
    db: Session, gestor, crear_convenio
):
    sin_marca = _formalizado(db, crear_convenio(gestor), activado=None)
    con_marca = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 5, 1))

    resultado = regularizar_codigos(db)

    assert resultado.sin_fecha_confiable == (sin_marca.id,)
    assert _codigos(db, sin_marca, con_marca) == [None, f"USB-ORI-{ANIO}-00001"]


def test_ca08_la_politica_de_anio_cubre_los_casos_sin_marca(
    db: Session, gestor, crear_convenio
):
    sin_marca = _formalizado(db, crear_convenio(gestor), activado=None)

    resultado = regularizar_codigos(db, anio_politica=ANIO)

    assert resultado.sin_fecha_confiable == ()
    assert _codigos(db, sin_marca) == [f"USB-ORI-{ANIO}-00001"]


def test_la_politica_de_anio_manda_sobre_el_anio_real(
    db: Session, gestor, crear_convenio
):
    convenio = _formalizado(db, crear_convenio(gestor), activado=_en(OTRO_ANIO, 5, 1))

    regularizar_codigos(db, anio_politica=ANIO)

    assert _codigos(db, convenio) == [f"USB-ORI-{ANIO}-00001"]


def test_ca08_asigna_un_lote_con_la_sesion_de_produccion(
    db: Session, gestor, crear_convenio
):
    """El lote completo con `autoflush` desactivado, como `SessionLocal`.

    Es el escenario real del procedimiento: reserva varios consecutivos dentro
    de una sola transacción. Con una implementación que dependa del autoflush,
    los tres convenios reciben el mismo código y el segundo choca contra el
    UNIQUE de `convenio.codigo`, de modo que CA-08 falla entero. Las demás
    pruebas de este archivo corren con autoflush activado y no lo detectan.
    """
    primero = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 3, 1))
    segundo = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 6, 1))
    tercero = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 9, 1))

    with db.no_autoflush:
        resultado = regularizar_codigos(db)

    assert [a.codigo for a in resultado.asignados] == [
        f"USB-ORI-{ANIO}-00001",
        f"USB-ORI-{ANIO}-00002",
        f"USB-ORI-{ANIO}-00003",
    ]
    assert _codigos(db, primero, segundo, tercero) == [
        f"USB-ORI-{ANIO}-00001",
        f"USB-ORI-{ANIO}-00002",
        f"USB-ORI-{ANIO}-00003",
    ]


# --- CA-08: idempotencia y respeto de lo existente ------------------------


def test_ca08_repetir_el_procedimiento_no_duplica_asignaciones(
    db: Session, gestor, crear_convenio
):
    convenio = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 5, 1))

    primera = regularizar_codigos(db)
    segunda = regularizar_codigos(db)

    assert len(primera.asignados) == 1
    assert segunda.asignados == ()
    assert _codigos(db, convenio) == [f"USB-ORI-{ANIO}-00001"]
    # Tampoco gasta un consecutivo en la segunda pasada.
    contador = db.scalar(
        select(ContadorCodigoConvenio).where(ContadorCodigoConvenio.anio == ANIO)
    )
    assert contador.ultimo_consecutivo == 1


def test_rn13_un_codigo_existente_no_se_reasigna(db: Session, gestor, crear_convenio):
    convenio = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 5, 1))
    convenio.codigo = "CONV-CARGADO-A-MANO"
    db.commit()

    resultado = regularizar_codigos(db)

    assert resultado.asignados == ()
    assert _codigos(db, convenio) == ["CONV-CARGADO-A-MANO"]


def test_un_convenio_en_tramite_no_recibe_codigo(db: Session, gestor, crear_convenio):
    # RN-01: el código es de los formalizados. Un convenio en trámite conserva
    # su identificación provisional.
    en_tramite = crear_convenio(gestor)
    assert en_tramite.estado == EstadoConvenio.EN_TRAMITE.value

    resultado = regularizar_codigos(db)

    assert resultado.asignados == ()
    assert _codigos(db, en_tramite) == [None]


# --- Simulación -----------------------------------------------------------


def test_la_simulacion_calcula_sin_persistir(db: Session, gestor, crear_convenio):
    convenio = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 5, 1))
    auditorias_antes = db.scalar(select(func.count()).select_from(Auditoria))

    resultado = regularizar_codigos(db, simular=True)

    # Informa el código exacto que asignaría...
    assert resultado.simulado is True
    assert [a.codigo for a in resultado.asignados] == [f"USB-ORI-{ANIO}-00001"]
    # ...y no deja nada: ni código, ni consecutivo, ni auditoría.
    assert _codigos(db, convenio) == [None]
    assert (
        db.scalar(
            select(func.count())
            .select_from(ContadorCodigoConvenio)
            .where(ContadorCodigoConvenio.anio == ANIO)
        )
        == 0
    )
    assert db.scalar(select(func.count()).select_from(Auditoria)) == auditorias_antes


# --- CA-08, CA-09: trazabilidad ------------------------------------------


def _auditoria_de_codigo(db: Session, convenio_id: int) -> Auditoria:
    registros = db.scalars(
        select(Auditoria).where(
            Auditoria.entidad == "convenio",
            Auditoria.registro_id == convenio_id,
            Auditoria.campo == "codigo",
        )
    ).all()
    assert len(registros) == 1
    return registros[0]


def test_ca08_registra_la_operacion_como_ejecucion_automatica(
    db: Session, gestor, crear_convenio
):
    convenio = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 5, 1))

    regularizar_codigos(db)

    registro = _auditoria_de_codigo(db, convenio.id)
    assert registro.ejecucion == EjecucionAuditoria.AUTOMATICA.value
    assert registro.evento == "CODIGO_REGULARIZADO"
    assert registro.valor_nuevo == f"USB-ORI-{ANIO}-00001"
    # Sin originador no se inventa un usuario (HT-09, RN-07).
    assert registro.usuario_id is None


def test_ca08_conserva_a_quien_autorizo_la_ejecucion(
    db: Session, gestor, crear_convenio, crear_usuario
):
    convenio = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 5, 1))
    administrador = crear_usuario(codigo_rol=CodigoRol.ADMINISTRADOR_ORI)

    regularizar_codigos(db, originador=administrador)

    registro = _auditoria_de_codigo(db, convenio.id)
    # El originador humano y la naturaleza automática son independientes.
    assert registro.usuario_id == administrador.id
    assert registro.rol == CodigoRol.ADMINISTRADOR_ORI.value
    assert registro.ejecucion == EjecucionAuditoria.AUTOMATICA.value


# --- Atomicidad -----------------------------------------------------------


def test_un_fallo_no_deja_asignaciones_parciales(
    db: Session, gestor, crear_convenio, monkeypatch
):
    primero = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 3, 1))
    segundo = _formalizado(db, crear_convenio(gestor), activado=_en(ANIO, 6, 1))

    llamadas = {"n": 0}
    real = regularizar_codigos.__globals__["asignar_codigo"]

    def falla_en_el_segundo(db_, convenio, anio):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("falla simulada a mitad del lote")
        return real(db_, convenio, anio)

    monkeypatch.setitem(
        regularizar_codigos.__globals__, "asignar_codigo", falla_en_el_segundo
    )
    with pytest.raises(RuntimeError):
        regularizar_codigos(db)
    monkeypatch.undo()

    # Ni el primero, que sí alcanzó a recibir código antes del fallo.
    assert _codigos(db, primero, segundo) == [None, None]
