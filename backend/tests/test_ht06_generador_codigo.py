"""HT-06 BE-01: generador institucional, consecutivo anual y unicidad.

Nivel servicio y función pura, sin HTTP. La asignación dentro de la
formalización se cubre en test_ht06_formalizacion_codigo.py y la concurrencia
en test_ht06_concurrencia_codigo.py.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.services.codigo_convenio import (
    asignar_codigo,
    formatear_codigo,
    siguiente_consecutivo,
)

# El formato se escribe a mano, sin derivarlo de PREFIJO_INSTITUCIONAL ni de
# DIGITOS_MINIMOS_CONSECUTIVO: un caso derivado de la constante que debe
# vigilar acompaña cualquier cambio de esa constante y deja de ser una prueba.
CODIGO_ESPERADO_PRIMERO = "USB-ORI-2026-00001"

# Años propios para las pruebas que tocan el contador. El consecutivo es global
# por año y hay pruebas que confirman de verdad sobre `db_engine` (la
# concurrencia de HU-15 formaliza y consume el consecutivo del año en curso),
# así que usar el año real ataría estas aserciones al orden de la suite.
ANIO = 2097
ANIO_SIGUIENTE = 2096
PRIMERO_DEL_ANIO = "USB-ORI-2097-00001"


# --- RN-03, RN-04, RN-06: nomenclatura aprobada ---------------------------


def test_formato_de_la_nomenclatura_aprobada() -> None:
    assert formatear_codigo(2026, 1) == CODIGO_ESPERADO_PRIMERO


@pytest.mark.parametrize(
    ("anio", "consecutivo", "esperado"),
    [
        pytest.param(2026, 1, "USB-ORI-2026-00001", id="primero-del-anio"),
        pytest.param(2026, 42, "USB-ORI-2026-00042", id="dos-digitos"),
        pytest.param(2026, 99999, "USB-ORI-2026-99999", id="ultimo-de-cinco-digitos"),
        pytest.param(2027, 1, "USB-ORI-2027-00001", id="otro-anio"),
    ],
)
def test_consecutivo_con_ceros_a_la_izquierda(
    anio: int, consecutivo: int, esperado: str
) -> None:
    assert formatear_codigo(anio, consecutivo) == esperado


# --- RN-12: pasado 99999 se amplía, no se trunca ni se repite --------------


def test_consecutivo_mayor_a_cinco_digitos_amplia_la_longitud() -> None:
    assert formatear_codigo(2026, 100000) == "USB-ORI-2026-100000"
    assert formatear_codigo(2026, 1234567) == "USB-ORI-2026-1234567"


def test_el_codigo_ampliado_no_repite_el_anterior() -> None:
    # Truncar a cinco dígitos haría que 100000 y 00000 compartieran código.
    assert formatear_codigo(2026, 100000) != formatear_codigo(2026, 0)


def test_el_codigo_cabe_en_la_columna() -> None:
    # convenio.codigo es String(40). Con siete dígitos de consecutivo el código
    # mide 24 caracteres, así que el margen cubre de sobra la vida del sistema.
    assert len(formatear_codigo(2026, 1234567)) <= 40


# --- CA-03, RN-07: consecutivo anual compartido ---------------------------


def test_el_consecutivo_avanza_dentro_del_mismo_anio(db: Session) -> None:
    assert [siguiente_consecutivo(db, ANIO) for _ in range(3)] == [1, 2, 3]


def test_cada_anio_empieza_su_propia_secuencia(db: Session) -> None:
    assert siguiente_consecutivo(db, ANIO) == 1
    assert siguiente_consecutivo(db, ANIO) == 2
    # CA-03: al cambiar de año comienza una secuencia nueva...
    assert siguiente_consecutivo(db, ANIO_SIGUIENTE) == 1
    # ...y el otro año conserva la suya donde estaba.
    assert siguiente_consecutivo(db, ANIO) == 3


def test_el_contador_crea_una_fila_por_anio(db: Session) -> None:
    siguiente_consecutivo(db, ANIO)
    siguiente_consecutivo(db, ANIO)
    siguiente_consecutivo(db, ANIO_SIGUIENTE)
    db.flush()

    contadores = db.scalars(
        select(ContadorCodigoConvenio)
        .where(ContadorCodigoConvenio.anio.in_([ANIO, ANIO_SIGUIENTE]))
        .order_by(ContadorCodigoConvenio.anio)
    ).all()
    assert [(c.anio, c.ultimo_consecutivo) for c in contadores] == [
        (ANIO_SIGUIENTE, 1),
        (ANIO, 2),
    ]


def test_varias_reservas_en_una_transaccion_sin_autoflush(db: Session) -> None:
    """Reserva repetida con la configuración de sesión de producción.

    `SessionLocal` tiene `autoflush=False`, pero el fixture `db` lo deja en el
    valor por omisión, que es True. Una implementación que lea la entidad para
    incrementarla en Python depende de ese autoflush: sin él, la segunda lectura
    de la misma transacción no ve el incremento pendiente y entrega otra vez el
    mismo número.

    Importa porque la regularización de convenios históricos reserva muchos
    consecutivos dentro de una sola transacción: con el mismo número para todos,
    el segundo convenio choca contra el UNIQUE de `convenio.codigo` y la
    operación entera falla. Ninguna otra prueba lo detecta, porque todas corren
    con autoflush activado.
    """
    with db.no_autoflush:
        valores = [siguiente_consecutivo(db, ANIO) for _ in range(4)]

    assert valores == [1, 2, 3, 4]


def test_un_anio_ya_sembrado_continua_donde_quedo(db: Session) -> None:
    db.add(ContadorCodigoConvenio(anio=ANIO, ultimo_consecutivo=7))
    db.flush()

    assert siguiente_consecutivo(db, ANIO) == 8


# --- RN-08: no se genera un código que ya exista -------------------------


def test_un_codigo_heredado_del_mismo_formato_no_se_vuelve_a_generar(
    db: Session, gestor, crear_convenio
) -> None:
    """El contador de un año nuevo arranca por encima de lo ya ocupado.

    Antes de que CA-05 cerrara el contrato de creación, HU-10 permitía teclear
    el código a mano. Un contador que naciera en cero generaría un código que
    ya existe y la formalización chocaría contra el UNIQUE de `convenio.codigo`,
    fallando con un error de servidor en el flujo principal.
    """
    crear_convenio(gestor, codigo=formatear_codigo(ANIO, 7))

    assert siguiente_consecutivo(db, ANIO) == 8


def test_un_codigo_heredado_de_otro_formato_no_reserva_nada(
    db: Session, gestor, crear_convenio
) -> None:
    # Un código cargado como CONV-0001 no es institucional y no ocupa ningún
    # número de la serie.
    crear_convenio(gestor, codigo="CONV-0001")

    assert siguiente_consecutivo(db, ANIO) == 1


def test_un_codigo_heredado_de_otro_anio_no_afecta_la_serie(
    db: Session, gestor, crear_convenio
) -> None:
    crear_convenio(gestor, codigo=formatear_codigo(ANIO_SIGUIENTE, 50))

    assert siguiente_consecutivo(db, ANIO) == 1
    assert siguiente_consecutivo(db, ANIO_SIGUIENTE) == 51


# --- CA-04, RN-08, RN-13: el código no se reasigna ------------------------


def test_asignar_codigo_usa_el_consecutivo_del_anio(db: Session, convenio_listo) -> None:
    assert asignar_codigo(db, convenio_listo, ANIO) == PRIMERO_DEL_ANIO
    assert convenio_listo.codigo == PRIMERO_DEL_ANIO


def test_un_convenio_con_codigo_conserva_el_suyo(db: Session, convenio_listo) -> None:
    asignar_codigo(db, convenio_listo, ANIO)

    # Repetir la asignación, incluso con otro año, devuelve el mismo código.
    assert asignar_codigo(db, convenio_listo, ANIO_SIGUIENTE) == PRIMERO_DEL_ANIO
    assert convenio_listo.codigo == PRIMERO_DEL_ANIO


def test_reasignar_no_consume_un_consecutivo(db: Session, convenio_listo) -> None:
    asignar_codigo(db, convenio_listo, ANIO)
    asignar_codigo(db, convenio_listo, ANIO)
    asignar_codigo(db, convenio_listo, ANIO)
    db.flush()

    # Un código ya entregado no gasta números del año: solo avanzó el primero.
    contador = db.scalar(
        select(ContadorCodigoConvenio).where(ContadorCodigoConvenio.anio == ANIO)
    )
    assert contador.ultimo_consecutivo == 1


def test_un_codigo_preexistente_no_se_sobrescribe(db: Session, convenio_listo) -> None:
    # RN-13: los convenios cargados a mano antes de HT-06 conservan su código.
    convenio_listo.codigo = "CONV-HISTORICO-001"

    assert asignar_codigo(db, convenio_listo, ANIO) == "CONV-HISTORICO-001"
    # Tampoco estrena el año: no hubo nada que numerar.
    assert (
        db.scalar(
            select(func.count())
            .select_from(ContadorCodigoConvenio)
            .where(ContadorCodigoConvenio.anio == ANIO)
        )
        == 0
    )


# --- CA-05: el código no se asigna ni se modifica a mano -----------------


def test_ca05_crear_desde_solicitud_rechaza_un_codigo_enviado(
    client, db, gestor, crear_convenio
) -> None:
    # Se reutiliza un convenio existente solo para tomar prestada su solicitud
    # aprobada: lo que se prueba es el contrato de creación.
    solicitud_id = crear_convenio(gestor).solicitud_id

    respuesta = client.post(
        "/api/convenios",
        json={
            "solicitud_id": solicitud_id,
            "objeto": "Convenio con código impuesto por el cliente",
            "codigo": "USB-ORI-2026-00001",
        },
    )

    assert respuesta.status_code == 422, respuesta.text


def test_ca05_crear_manualmente_rechaza_un_codigo_enviado(client, gestor) -> None:
    respuesta = client.post(
        "/api/convenios/manual",
        json={
            "objeto": "Convenio manual con código impuesto",
            "codigo": "USB-ORI-2026-00001",
        },
    )

    assert respuesta.status_code == 422, respuesta.text


def test_ca05_actualizar_la_elaboracion_rechaza_un_codigo_enviado(
    client, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}/elaboracion",
        json={"expected_revision": 0, "codigo": "USB-ORI-2026-00001"},
    )

    assert respuesta.status_code == 422, respuesta.text
