"""HU-38: sesiones PostgreSQL independientes, sin simular el candado SQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.enums import CodigoGuia, EstadoGuia
from backend.models.estado_guia_usuario import EstadoGuiaUsuario
from backend.models.rol import Rol
from backend.models.usuario import Usuario
from backend.services.guias import ServicioGuias


@pytest.fixture
def usuario_confirmado(db_engine):
    # Los hilos necesitan una cuenta confirmada fuera de la transacción del
    # fixture db. Se eliminan únicamente las filas creadas por esta prueba.
    with Session(db_engine) as db:
        rol = db.scalar(select(Rol).where(Rol.codigo == CodigoRol.SOLICITANTE_EXTERNO))
        usuario = Usuario(correo=f"hu38-{uuid4().hex}@example.test", hash_contrasena="no-login",
                          nombre_completo="Concurrencia HU-38", rol=rol, tipo_usuario=TipoUsuario.EXTERNO)
        db.add(usuario)
        db.commit()
        usuario_id = usuario.id
    try:
        yield usuario_id
    finally:
        with Session(db_engine) as db:
            db.execute(delete(EstadoGuiaUsuario).where(EstadoGuiaUsuario.usuario_id == usuario_id))
            db.execute(delete(Usuario).where(Usuario.id == usuario_id))
            db.commit()


@pytest.mark.parametrize("estado_inicial", [None, EstadoGuia.OMITIDO, EstadoGuia.COMPLETADO])
@pytest.mark.parametrize("estados", [
    (EstadoGuia.COMPLETADO, EstadoGuia.OMITIDO),
    (EstadoGuia.OMITIDO, EstadoGuia.COMPLETADO),
    (EstadoGuia.COMPLETADO, EstadoGuia.COMPLETADO),
])
def test_dos_dispositivos_conservan_completado_y_una_sola_fila(
    db_engine, usuario_confirmado, estado_inicial, estados
):
    if estado_inicial:
        with Session(db_engine) as db:
            ServicioGuias(db).registrar(db.get(Usuario, usuario_confirmado),
                                       CodigoGuia.ONBOARDING_INICIAL, estado_inicial, 1)
    barrera = Barrier(2)

    def guardar(estado):
        with Session(db_engine) as db:
            db.execute(select(func.set_config("lock_timeout", "10000", True)))
            usuario = db.get(Usuario, usuario_confirmado)
            barrera.wait(timeout=10)
            return ServicioGuias(db).registrar(usuario, CodigoGuia.ONBOARDING_INICIAL, estado, 1)

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(guardar, estados))
    assert all(resultado.estado in {EstadoGuia.COMPLETADO, EstadoGuia.OMITIDO} for resultado in resultados)
    with Session(db_engine) as db:
        registros = list(db.scalars(select(EstadoGuiaUsuario).where(
            EstadoGuiaUsuario.usuario_id == usuario_confirmado)))
        assert len(registros) == 1
        assert registros[0].estado == EstadoGuia.COMPLETADO
