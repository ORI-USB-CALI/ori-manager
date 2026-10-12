from backend.core.roles import CodigoRol


def test_exportar_convenio_pdf_exitoso(
    client, convenio_listo, entrar_como, gestor
) -> None:
    entrar_como(gestor)

    # Probar endpoint BE-04 (/api/v1/convenios/{id}/exportar)
    response = client.get(f"/api/v1/convenios/{convenio_listo.id}/exportar?formato=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="Convenio_' in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.pdf"')
    assert response.content.startswith(b"%PDF-")

    # Probar compatibilidad con /api/convenios/{id}/exportar
    response_api = client.get(
        f"/api/convenios/{convenio_listo.id}/exportar?formato=pdf"
    )
    assert response_api.status_code == 200
    assert response_api.content.startswith(b"%PDF-")


def test_exportar_convenio_excel_exitoso(
    client, convenio_listo, entrar_como, gestor
) -> None:
    entrar_como(gestor)

    response = client.get(
        f"/api/v1/convenios/{convenio_listo.id}/exportar?formato=excel"
    )
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert 'attachment; filename="Convenio_' in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.xlsx"')
    # Archivos XLSX son archivos ZIP que inician con la firma PK\x03\x04
    assert response.content.startswith(b"PK")


def test_exportar_convenio_formato_invalido(
    client, convenio_listo, entrar_como, gestor
) -> None:
    entrar_como(gestor)

    response = client.get(
        f"/api/v1/convenios/{convenio_listo.id}/exportar?formato=invalido"
    )
    assert response.status_code == 400
    assert "Formato no válido" in response.json()["detail"]


def test_exportar_convenio_autorizacion(
    client, convenio_listo, crear_usuario, entrar_como
) -> None:
    # 1. Sin autenticación -> 401 Unauthorized
    client.cookies.clear()
    res_no_auth = client.get(
        f"/api/v1/convenios/{convenio_listo.id}/exportar?formato=pdf"
    )
    assert res_no_auth.status_code == 401

    # 2. Con usuario sin permiso de convenios (SOLICITANTE_INTERNO) -> 403 Forbidden
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
    entrar_como(solicitante)
    res_forbidden = client.get(
        f"/api/v1/convenios/{convenio_listo.id}/exportar?formato=pdf"
    )
    assert res_forbidden.status_code == 403


def test_exportar_convenio_no_encontrado(client, entrar_como, gestor) -> None:
    entrar_como(gestor)

    response = client.get("/api/v1/convenios/999999/exportar?formato=pdf")
    assert response.status_code == 404


def test_exportar_convenio_datos_insuficientes_ca03(
    client, db, entrar_como, gestor, crear_convenio
) -> None:
    entrar_como(gestor)

    # Crear convenio y forzar objeto vacío en base de datos para simular datos insuficientes (CA-03)
    convenio = crear_convenio(gestor)
    convenio.objeto = None
    db.commit()

    response = client.get(f"/api/v1/convenios/{convenio.id}/exportar?formato=pdf")
    assert response.status_code == 422
    data = response.json()
    assert "faltantes" in data["detail"]
    assert "objeto" in data["detail"]["faltantes"]
