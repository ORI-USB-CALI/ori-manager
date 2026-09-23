from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario


@pytest.fixture
def unidades_registro(db):
    activas = [
        UnidadOrganizacional(
            codigo=f"REG-{tipo.value}",
            nombre=f"Unidad {tipo.value}",
            tipo=tipo.value,
            activa=True,
        )
        for tipo in TipoUnidad
    ]
    inactiva = UnidadOrganizacional(
        codigo="REG-INACTIVA",
        nombre="Unidad inactiva",
        tipo=TipoUnidad.FACULTAD.value,
        activa=False,
    )
    db.add_all([*activas, inactiva])
    db.commit()
    return activas, inactiva


def _datos_interno(correo: str, unidad_id: int) -> dict[str, object]:
    return {
        "correo": correo,
        "contrasena": "ClaveSegura123",
        "confirmacion_contrasena": "ClaveSegura123",
        "nombre_completo": "Solicitante interno",
        "cargo": "Docente",
        "unidad_organizacional_id": unidad_id,
    }


def _datos_externo(correo: str = "persona@example.com") -> dict[str, object]:
    return {
        "correo": correo,
        "contrasena": "ClaveSegura123",
        "confirmacion_contrasena": "ClaveSegura123",
        "nombre_completo": "Solicitante externo",
        "documento_identidad": "CE-123",
        "entidad_externa": "Entidad externa",
        "cargo": "Directora",
    }


@pytest.mark.parametrize(
    "correo",
    ["persona@correo.usbcali.edu.co", "persona@usbcali.edu.co"],
)
def test_dominio_institucional_crea_solicitante_interno(
    correo, db, client, unidades_registro
):
    activas, _ = unidades_registro

    respuesta = client.post(
        "/api/auth/registro", json=_datos_interno(correo, activas[0].id)
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["tipo_usuario"] == TipoUsuario.INTERNO
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    assert usuario is not None
    assert usuario.tipo_usuario == TipoUsuario.INTERNO
    assert usuario.rol.codigo == CodigoRol.SOLICITANTE_INTERNO
    assert usuario.unidad_organizacional_id == activas[0].id
    assert usuario.entidad_externa is None
    assert usuario.correo_verificado_en is None


@pytest.mark.parametrize(
    "correo", ["persona@example.com", "persona@usbcali.edu.co.evil.com"]
)
def test_otro_dominio_crea_solicitante_externo(correo, db, client):
    respuesta = client.post("/api/auth/registro", json=_datos_externo(correo))

    assert respuesta.status_code == 201
    assert respuesta.json()["tipo_usuario"] == TipoUsuario.EXTERNO
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    assert usuario is not None
    assert usuario.tipo_usuario == TipoUsuario.EXTERNO
    assert usuario.rol.codigo == CodigoRol.SOLICITANTE_EXTERNO
    assert usuario.unidad_organizacional_id is None
    assert usuario.documento_identidad == "CE-123"
    assert usuario.entidad_externa == "Entidad externa"
    assert usuario.correo_verificado_en is None


@pytest.mark.parametrize("campo", ["rol", "tipo_usuario"])
def test_registro_no_acepta_rol_ni_tipo(campo, db, client):
    datos = {**_datos_externo(), campo: "ADMINISTRADOR_ORI"}
    cantidad_antes = db.scalar(select(func.count()).select_from(Usuario))

    respuesta = client.post("/api/auth/registro", json=datos)

    assert respuesta.status_code == 422
    assert db.scalar(select(func.count()).select_from(Usuario)) == cantidad_antes


def test_interno_exige_cargo_y_unidad_activa(client, unidades_registro):
    activas, inactiva = unidades_registro
    sin_cargo = _datos_interno("sin-cargo@usbcali.edu.co", activas[0].id)
    sin_cargo.pop("cargo")

    assert client.post("/api/auth/registro", json=sin_cargo).status_code == 422
    assert (
        client.post(
            "/api/auth/registro",
            json=_datos_interno("inactiva@usbcali.edu.co", inactiva.id),
        ).status_code
        == 422
    )


@pytest.mark.parametrize("campo", ["documento_identidad", "entidad_externa", "cargo"])
def test_externo_exige_documento_entidad_y_cargo(campo, client):
    datos = _datos_externo(f"sin-{campo}@example.com")
    datos.pop(campo)

    assert client.post("/api/auth/registro", json=datos).status_code == 422


def test_campos_del_tipo_opuesto_no_se_guardan(db, client, unidades_registro):
    activas, _ = unidades_registro
    interno = {
        **_datos_interno("limpio@usbcali.edu.co", activas[0].id),
        "entidad_externa": "No debe persistir",
        "documento_identidad": "No debe persistir",
    }
    externo = {
        **_datos_externo("limpio@example.com"),
        "unidad_organizacional_id": activas[0].id,
    }

    assert client.post("/api/auth/registro", json=interno).status_code == 201
    assert client.post("/api/auth/registro", json=externo).status_code == 201
    usuario_interno = db.scalar(
        select(Usuario).where(Usuario.correo == "limpio@usbcali.edu.co")
    )
    usuario_externo = db.scalar(
        select(Usuario).where(Usuario.correo == "limpio@example.com")
    )
    assert usuario_interno is not None and usuario_interno.entidad_externa is None
    assert usuario_interno.documento_identidad is None
    assert (
        usuario_externo is not None and usuario_externo.unidad_organizacional_id is None
    )


def test_correo_duplicado_no_crea_usuario_y_orienta_siguiente_paso(db, client):
    datos = _datos_externo("duplicado-registro@example.com")
    assert client.post("/api/auth/registro", json=datos).status_code == 201

    duplicado = client.post("/api/auth/registro", json=datos)

    assert duplicado.status_code == 409
    assert duplicado.json()["detail"]["siguiente_paso"] == "VERIFICAR_CORREO"
    cantidad = db.scalar(
        select(func.count())
        .select_from(Usuario)
        .where(Usuario.correo == datos["correo"])
    )
    assert cantidad == 1


def test_registro_rechaza_passwords_diferentes_y_minimo(client):
    diferentes = {
        **_datos_externo("diferentes@example.com"),
        "confirmacion_contrasena": "OtraClave123",
    }
    corta = {
        **_datos_externo("corta@example.com"),
        "contrasena": "corta",
        "confirmacion_contrasena": "corta",
    }

    assert client.post("/api/auth/registro", json=diferentes).status_code == 422
    assert client.post("/api/auth/registro", json=corta).status_code == 422


def test_login_rechaza_solicitante_no_verificado(client):
    datos = _datos_externo("pendiente@example.com")
    assert client.post("/api/auth/registro", json=datos).status_code == 201

    respuesta = client.post(
        "/api/auth/login",
        json={"correo": datos["correo"], "contrasena": datos["contrasena"]},
    )

    assert respuesta.status_code == 403
    assert "verificar" in respuesta.json()["detail"].lower()
    assert respuesta.cookies.get("session_id") is None


@pytest.mark.parametrize(
    "rol",
    [CodigoRol.SOLICITANTE_INTERNO, CodigoRol.SOLICITANTE_EXTERNO],
)
def test_admin_no_puede_crear_roles_solicitantes(
    rol, client, crear_usuario, entrar_como
):
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))
    datos = {
        "correo": f"{rol.value.lower()}@example.com",
        "contrasena": "ClaveSegura123",
        "nombre_completo": "No permitido",
        "rol": rol.value,
        "tipo_usuario": TipoUsuario.INTERNO.value,
    }

    respuesta = client.post("/api/usuarios", json=datos)

    assert respuesta.status_code == 422
    assert "roles operativos" in respuesta.json()["detail"]


@pytest.mark.parametrize(
    "rol",
    [CodigoRol.SOLICITANTE_INTERNO, CodigoRol.SOLICITANTE_EXTERNO],
)
def test_admin_no_puede_asignar_roles_solicitantes(
    rol, client, crear_usuario, entrar_como
):
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    operativo = crear_usuario(CodigoRol.GESTOR_ORI)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{operativo.id}/rol", json={"rol": rol.value}
    )

    assert respuesta.status_code == 422
    assert "roles operativos" in respuesta.json()["detail"]


def test_admin_crea_usuario_operativo_verificado(
    db, client, crear_usuario, entrar_como
):
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))
    datos = {
        "correo": "operativo-verificado@example.com",
        "contrasena": "ClaveSegura123",
        "nombre_completo": "Gestor verificado",
        "rol": CodigoRol.GESTOR_ORI.value,
        "tipo_usuario": TipoUsuario.INTERNO.value,
    }

    assert client.post("/api/usuarios", json=datos).status_code == 201
    usuario = db.scalar(
        select(Usuario).where(Usuario.correo == "operativo-verificado@example.com")
    )
    assert usuario is not None and usuario.correo_verificado_en is not None


def test_catalogo_publico_solo_expone_unidades_activas_y_campos_permitidos(
    client, unidades_registro
):
    activas, inactiva = unidades_registro

    respuesta = client.get("/api/auth/registro/unidades")

    assert respuesta.status_code == 200
    assert {item["id"] for item in respuesta.json()} == {item.id for item in activas}
    assert all(set(item) == {"id", "nombre", "tipo"} for item in respuesta.json())
    assert inactiva.id not in {item["id"] for item in respuesta.json()}


def test_sql_migracion_marca_usuarios_existentes_como_verificados(db, crear_usuario):
    usuario = crear_usuario(correo="existente-migracion@example.com")
    usuario.correo_verificado_en = None
    db.commit()
    ruta = (
        Path(__file__).parents[1]
        / "migrations/versions/b822d14c8a31_hu08_correo_verificado.py"
    )
    spec = spec_from_file_location("migracion_hu08", ruta)
    assert spec is not None and spec.loader is not None
    migracion = module_from_spec(spec)
    spec.loader.exec_module(migracion)

    db.execute(text(migracion.MARCAR_EXISTENTES_SQL))
    db.flush()
    db.refresh(usuario)

    assert usuario.correo_verificado_en is not None


def test_crud_administrativo_excluye_solicitantes_legacy(
    db, client, crear_usuario, entrar_como
):
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    solicitantes = [
        crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ]
    entrar_como(admin)

    listado = client.get("/api/usuarios")

    assert listado.status_code == 200
    ids = {usuario["id"] for usuario in listado.json()}
    assert admin.id in ids
    assert all(solicitante.id not in ids for solicitante in solicitantes)
    for solicitante in solicitantes:
        assert client.get(f"/api/usuarios/{solicitante.id}").status_code == 404
        assert (
            client.patch(
                f"/api/usuarios/{solicitante.id}",
                json={"cargo": "No permitido"},
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"/api/usuarios/{solicitante.id}/rol",
                json={"rol": CodigoRol.GESTOR_ORI.value},
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"/api/usuarios/{solicitante.id}/estado",
                json={"activo": False},
            ).status_code
            == 404
        )
        db.refresh(solicitante)
        assert solicitante.cargo is None
        assert solicitante.activo is True
        assert solicitante.rol.codigo in {
            CodigoRol.SOLICITANTE_INTERNO,
            CodigoRol.SOLICITANTE_EXTERNO,
        }


@pytest.mark.parametrize(
    "rol",
    [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI, CodigoRol.REVISOR_ORI],
)
def test_crud_administrativo_conserva_usuarios_operativos(
    rol, client, crear_usuario, entrar_como
):
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    operativo = crear_usuario(rol)
    entrar_como(admin)

    listado = client.get("/api/usuarios")
    detalle = client.get(f"/api/usuarios/{operativo.id}")
    edicion = client.patch(
        f"/api/usuarios/{operativo.id}", json={"cargo": "Cargo actualizado"}
    )

    assert operativo.id in {usuario["id"] for usuario in listado.json()}
    assert detalle.status_code == 200
    assert edicion.status_code == 200
    assert edicion.json()["cargo"] == "Cargo actualizado"
