"""HT-06 BE-03: unicidad del código bajo formalizaciones simultáneas.

CA-03 y RN-11. El candado `FOR UPDATE` que `formalizar()` ya tiene sobre el
convenio no sirve aquí: dos convenios distintos no se bloquean entre sí y
comparten el consecutivo del año, así que el contador necesita su propio
candado.

Estas pruebas usan `db_engine` con sesiones reales que confirman de verdad, el
mismo patrón de test_renovacion_tardia_concurrencia.py y de la concurrencia de
HU-15. Por eso limpian a mano en `finally`, incluida la fila del contador: lo
que confirman no lo revierte el fixture `db`.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker
from test_hu15_revision_final_firmas import (
    _crear_escenario_concurrente,
    _limpiar_escenario_concurrente,
)

from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import EstadoFirmaConvenio, ModalidadFirma
from backend.models.usuario import Usuario
from backend.services import firmas as servicio_firmas
from backend.services.codigo_convenio import siguiente_consecutivo
from backend.services.firmas import ServicioFirmas

# Año propio para no cruzarse con el consecutivo que consumen otras pruebas que
# también confirman de verdad. La fila se borra al terminar.
ANIO = 2098


@pytest.fixture(autouse=True)
def anio_fijo(monkeypatch) -> None:
    # Los hilos ven el parche porque es un atributo del módulo.
    monkeypatch.setattr(
        servicio_firmas, "fecha_actual_dominio", lambda: date(ANIO, 6, 15)
    )


def _preparar_para_formalizar(db_engine, escenario: dict[str, object]) -> None:
    """Lleva el escenario hasta tener las siete firmas registradas.

    Replica la preparación de test_formalizaciones_concurrentes_producen_un_unico_cierre:
    `_crear_escenario_concurrente` deja el convenio en revisión final.
    """
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    with fabrica() as sesion:
        gestor = sesion.get(Usuario, int(escenario["gestor_id"]))
        assert gestor is not None
        proceso = ServicioFirmas(sesion).aprobar_revision_final(
            int(escenario["convenio_id"]),
            int(escenario["version_numero"]),
            gestor,
        )
        for firma in proceso.firmas:
            ServicioFirmas(sesion).configurar_firma(
                int(escenario["convenio_id"]),
                firma.id,
                f"Firmante {firma.id}",
                "Cargo institucional",
                None,
                ModalidadFirma.FISICA,
            )
        proceso = ServicioFirmas(sesion).iniciar(int(escenario["convenio_id"]))
        documento = Documento(
            convenio_id=int(escenario["convenio_id"]),
            tipo="CONVENIO_FIRMADO",
            nombre_archivo="ht06-concurrente.pdf",
            ruta_almacenamiento=f"pruebas/{uuid4().hex}.pdf",
            tipo_mime="application/pdf",
            tamano_bytes=20,
            es_vigente=True,
            cargado_por_id=gestor.id,
        )
        sesion.add(documento)
        sesion.flush()
        for firma in proceso.firmas:
            firma.estado = EstadoFirmaConvenio.FIRMADA.value
            firma.fecha_firma = datetime.now(UTC)
            firma.documento_id = documento.id
        sesion.commit()


def _borrar_contador(db_engine) -> None:
    fabrica = sessionmaker(bind=db_engine)
    with fabrica() as sesion:
        sesion.execute(
            delete(ContadorCodigoConvenio).where(ContadorCodigoConvenio.anio == ANIO)
        )
        sesion.commit()


def _sembrar_contador(db_engine, ultimo_consecutivo: int = 0) -> None:
    """Deja la fila del año ya confirmada.

    Importa para que la carrera sea real: cuando la fila no existe, el
    `INSERT ... ON CONFLICT DO NOTHING` serializa a los competidores por sí
    solo (el segundo espera en el índice único), y entonces la prueba pasaría
    incluso sin el `FOR UPDATE` que debe vigilar.
    """
    fabrica = sessionmaker(bind=db_engine)
    with fabrica() as sesion:
        sesion.add(
            ContadorCodigoConvenio(anio=ANIO, ultimo_consecutivo=ultimo_consecutivo)
        )
        sesion.commit()


def test_ca03_dos_formalizaciones_simultaneas_reciben_codigos_distintos(db_engine):
    """Comprobación de extremo a extremo, sobre `formalizar()` completa.

    No garantiza que las dos transacciones coincidan dentro de la reserva del
    consecutivo: la barrera solo sincroniza el arranque y cada formalización
    hace mucho trabajo antes de llegar al contador. El candado lo vigilan
    `test_ca03_dos_reservas_simultaneas_no_repiten_el_consecutivo` y su
    variante de cuatro hilos; esto confirma que la pieza encaja en la
    operación real y que cada convenio se lleva su propio código.
    """
    primero = _crear_escenario_concurrente(db_engine)
    segundo = _crear_escenario_concurrente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    try:
        _preparar_para_formalizar(db_engine, primero)
        _preparar_para_formalizar(db_engine, segundo)
        # Con la fila del año ya creada, la carrera no se apoya en el
        # ON CONFLICT del estreno.
        _sembrar_contador(db_engine)

        barrera = Barrier(2)

        def formalizar(escenario: dict[str, object]) -> str:
            with fabrica() as sesion:
                gestor = sesion.get(Usuario, int(escenario["gestor_id"]))
                assert gestor is not None
                barrera.wait(timeout=10)
                ServicioFirmas(sesion).formalizar(
                    int(escenario["convenio_id"]), gestor
                )
                convenio = sesion.get(Convenio, int(escenario["convenio_id"]))
                return convenio.codigo

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            codigos = list(ejecutor.map(formalizar, [primero, segundo]))

        # Ninguna de las dos falla y cada una se lleva su propio consecutivo:
        # el contador las serializa en lugar de hacer chocar el UNIQUE.
        assert sorted(codigos) == [
            f"USB-ORI-{ANIO}-00001",
            f"USB-ORI-{ANIO}-00002",
        ]

        with fabrica() as verificacion:
            contador = verificacion.scalar(
                select(ContadorCodigoConvenio).where(
                    ContadorCodigoConvenio.anio == ANIO
                )
            )
            # Dos códigos entregados, dos consecutivos consumidos: ni se repiten
            # ni se salta ninguno.
            assert contador.ultimo_consecutivo == 2
            persistidos = verificacion.scalars(
                select(Convenio.codigo).where(
                    Convenio.id.in_(
                        [int(primero["convenio_id"]), int(segundo["convenio_id"])]
                    )
                )
            ).all()
            assert sorted(persistidos) == sorted(codigos)
    finally:
        _limpiar_escenario_concurrente(db_engine, primero)
        _limpiar_escenario_concurrente(db_engine, segundo)
        _borrar_contador(db_engine)


def _reservar_en_paralelo(db_engine, veces: int) -> list[int]:
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    barrera = Barrier(veces)

    def reservar(_) -> int:
        with fabrica() as sesion:
            # Dentro de la transacción y justo antes de tocar el contador, para
            # que los competidores lleguen al candado a la vez.
            sesion.execute(select(ContadorCodigoConvenio).limit(0))
            barrera.wait(timeout=10)
            valor = siguiente_consecutivo(sesion, ANIO)
            sesion.commit()
            return valor

    with ThreadPoolExecutor(max_workers=veces) as ejecutor:
        return list(ejecutor.map(reservar, range(veces)))


def test_ca03_dos_reservas_simultaneas_no_repiten_el_consecutivo(db_engine):
    """La prueba que vigila el candado del contador.

    Con la fila ya creada, dos transacciones simultáneas leen, incrementan y
    confirman. Sin `FOR UPDATE` ambas verían el mismo valor de partida y
    entregarían el mismo consecutivo.
    """
    _sembrar_contador(db_engine, ultimo_consecutivo=10)
    try:
        valores = _reservar_en_paralelo(db_engine, veces=2)

        assert sorted(valores) == [11, 12], "el consecutivo se entregó dos veces"
    finally:
        _borrar_contador(db_engine)


def test_ca03_varias_reservas_simultaneas_no_dejan_huecos(db_engine):
    _sembrar_contador(db_engine)
    try:
        valores = _reservar_en_paralelo(db_engine, veces=4)

        assert sorted(valores) == [1, 2, 3, 4]

        fabrica = sessionmaker(bind=db_engine)
        with fabrica() as verificacion:
            contador = verificacion.scalar(
                select(ContadorCodigoConvenio).where(
                    ContadorCodigoConvenio.anio == ANIO
                )
            )
            assert contador.ultimo_consecutivo == 4
    finally:
        _borrar_contador(db_engine)


def test_rn11_el_contador_estrena_el_anio_una_sola_vez(db_engine):
    """Dos transacciones que estrenan el mismo año no duplican su fila.

    Aquí la fila NO se siembra a propósito: se prueba el camino del
    `INSERT ... ON CONFLICT DO NOTHING`, donde la segunda espera a que la
    primera confirme y entonces no inserta nada.
    """
    try:
        valores = _reservar_en_paralelo(db_engine, veces=2)

        assert sorted(valores) == [1, 2]

        fabrica = sessionmaker(bind=db_engine)
        with fabrica() as verificacion:
            filas = verificacion.scalars(
                select(ContadorCodigoConvenio).where(
                    ContadorCodigoConvenio.anio == ANIO
                )
            ).all()
            assert len(filas) == 1
            assert filas[0].ultimo_consecutivo == 2
    finally:
        _borrar_contador(db_engine)
