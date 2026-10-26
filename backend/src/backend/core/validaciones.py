"""HT-14. Reglas de formato de los datos registrados en una solicitud.

Cada función recibe el valor escrito por el usuario y devuelve su forma
canónica, o lanza ``ValueError`` con un mensaje para mostrar junto al campo.
Los casos válidos e inválidos de cada regla están en
``tests/test_ht14_validaciones.py``.
"""

import re

import phonenumbers

from backend.models.enums import TipoIdentificacion

# Pesos de la DIAN para el dígito de verificación, desde el dígito de la derecha.
_PESOS_DV_NIT = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)

_SEPARADORES_NUMERICOS = re.compile(r"[.\s]")
_BASE_NUMERICA = re.compile(r"\d{5,10}")
_DIGITO = re.compile(r"\d")
_CEDULA_EXTRANJERIA = re.compile(r"[A-Z0-9]{3,15}")
_PASAPORTE = re.compile(r"[A-Z0-9]{5,20}")
_IDENTIFICACION_LIBRE = re.compile(r"[A-Za-z0-9\-./ ]{3,40}")

# phonenumbers convierte letras en dígitos (teclados alfabéticos); CA-02 exige
# rechazarlas, así que los caracteres se revisan antes de interpretar el número.
_TELEFONO = re.compile(
    r"\+?[\d\s\-().]+(?:\s*(?:ext\.?|extensi[oó]n|x)\s*\d{1,6})?", re.IGNORECASE
)
_REGION_POR_DEFECTO = "CO"

_CIUDAD = re.compile(r"[^\W\d_](?:[^\W\d_]|[\s\-.'])*")
_LETRA = re.compile(r"[^\W\d_]")
_DIRECCION = re.compile(r"(?:[^\W_]|[\s#\-.,/°º()'])+")


def _colapsar_espacios(valor: str) -> str:
    return " ".join(valor.split())


def calcular_digito_verificacion_nit(base: str) -> int:
    suma = sum(
        int(digito) * peso
        for digito, peso in zip(reversed(base), _PESOS_DV_NIT, strict=False)
    )
    residuo = suma % 11
    return residuo if residuo < 2 else 11 - residuo


def normalizar_digito_verificacion_nit(base: str, valor: str) -> str:
    """El DV se registra en su propio campo y debe coincidir con el de la DIAN."""
    digito = valor.strip()
    if not _DIGITO.fullmatch(digito):
        raise ValueError("El dígito de verificación debe ser un solo dígito")
    if int(digito) != calcular_digito_verificacion_nit(base):
        raise ValueError("El dígito de verificación del NIT no es correcto")
    return digito


def normalizar_identificacion(tipo: TipoIdentificacion, valor: str) -> str:
    """CA-01 y RN-04: cada tipo de identificación tiene su propia regla.

    Para NIT y cédula de ciudadanía se devuelve solo la base numérica: es el
    valor que se guarda y con el que se buscan aliados. El DV del NIT se valida
    aparte con ``normalizar_digito_verificacion_nit``.
    """
    if tipo == TipoIdentificacion.NIT:
        base = _SEPARADORES_NUMERICOS.sub("", valor)
        if not _BASE_NUMERICA.fullmatch(base):
            raise ValueError(
                "El NIT debe tener entre 5 y 10 dígitos, sin el dígito de "
                "verificación (se registra en su propio campo)"
            )
        return base
    if tipo == TipoIdentificacion.CEDULA_CIUDADANIA:
        cedula = _SEPARADORES_NUMERICOS.sub("", valor)
        if not _BASE_NUMERICA.fullmatch(cedula):
            raise ValueError("La cédula de ciudadanía debe tener entre 5 y 10 dígitos")
        return cedula
    if tipo == TipoIdentificacion.CEDULA_EXTRANJERIA:
        cedula = re.sub(r"\s", "", valor).upper()
        if not _CEDULA_EXTRANJERIA.fullmatch(cedula):
            raise ValueError(
                "La cédula de extranjería debe tener entre 3 y 15 letras o dígitos"
            )
        return cedula
    if tipo == TipoIdentificacion.PASAPORTE:
        pasaporte = re.sub(r"\s", "", valor).upper()
        if not _PASAPORTE.fullmatch(pasaporte):
            raise ValueError("El pasaporte debe tener entre 5 y 20 letras o dígitos")
        return pasaporte
    identificacion = _colapsar_espacios(valor)
    if not _IDENTIFICACION_LIBRE.fullmatch(identificacion):
        raise ValueError(
            "La identificación debe tener entre 3 y 40 caracteres: letras, "
            "dígitos, espacios, guion, punto o barra"
        )
    return identificacion


def normalizar_telefono(valor: str) -> str:
    """CA-02 y RN-05: plan de numeración del país; sin indicativo, Colombia."""
    telefono = valor.strip()
    mensaje = (
        "Ingrese un teléfono válido. Para números fuera de Colombia, "
        "incluya el indicativo con + (por ejemplo, +34 912 345 678)"
    )
    if not _TELEFONO.fullmatch(telefono):
        raise ValueError(mensaje)
    try:
        numero = phonenumbers.parse(telefono, _REGION_POR_DEFECTO)
    except phonenumbers.NumberParseException as error:
        raise ValueError(mensaje) from error
    if not phonenumbers.is_valid_number(numero):
        raise ValueError(mensaje)
    canonico = phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)
    # E.164 no admite extensiones; se conservan con la sintaxis de RFC 3966.
    return f"{canonico};ext={numero.extension}" if numero.extension else canonico


def normalizar_ciudad(valor: str) -> str:
    """CA-03: sin fuente confiable de localidades, solo se valida el texto."""
    ciudad = _colapsar_espacios(valor)
    if not (2 <= len(ciudad) <= 120 and _CIUDAD.fullmatch(ciudad)):
        raise ValueError(
            "La ciudad debe tener entre 2 y 120 caracteres y contener solo "
            "letras, espacios, guion, punto o apóstrofo"
        )
    return ciudad


def normalizar_direccion(valor: str) -> str:
    """CA-04, RN-07 y RN-08: estructura razonable, sin nomenclatura obligatoria."""
    direccion = _colapsar_espacios(valor)
    if not (
        5 <= len(direccion) <= 200
        and _DIRECCION.fullmatch(direccion)
        and _LETRA.search(direccion)
    ):
        raise ValueError(
            "La dirección debe tener entre 5 y 200 caracteres, incluir letras "
            "y usar solo letras, dígitos, espacios y los signos # - . , / ° ( )"
        )
    return direccion


def identificacion_completa(
    tipo: str | None, base: str | None, digito_verificacion: str | None
) -> str | None:
    """Identificación para mostrar: el NIT se acompaña de su DV cuando existe."""
    if base and tipo == TipoIdentificacion.NIT and digito_verificacion:
        return f"{base}-{digito_verificacion}"
    return base
