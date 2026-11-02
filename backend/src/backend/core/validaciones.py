"""HT-14. Reglas de formato de los datos registrados en una solicitud.

Cada función recibe el valor escrito por el usuario y devuelve su forma
canónica, o lanza ``ValueError`` con un mensaje para mostrar junto al campo.
Los casos válidos e inválidos de cada regla están en
``tests/test_ht14_validaciones.py``.
"""

import re
import unicodedata

import phonenumbers

from backend.models.enums import TipoIdentificacion

# Pesos de la DIAN para el dígito de verificación, desde el dígito de la derecha.
_PESOS_DV_NIT = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)

# H-07: solo los 17 espacios horizontales Unicode Zs; nunca controles C0/C1,
# separadores de línea/párrafo ni caracteres de formato como BOM/ancho cero.
ESPACIOS_FORMATO = " \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
_ESPACIOS_FORMATO = re.compile(f"[{re.escape(ESPACIOS_FORMATO)}]+")
_SEPARADORES_NUMERICOS = re.compile(f"[.{re.escape(ESPACIOS_FORMATO)}]")
_BASE_NUMERICA = re.compile(r"[0-9]{5,10}")
_DIGITO = re.compile(r"[0-9]")
_CEDULA_EXTRANJERIA = re.compile(r"[A-Z0-9]{3,15}")
_PASAPORTE = re.compile(r"[A-Z0-9]{5,20}")
_IDENTIFICACION_LIBRE = re.compile(r"[A-Za-z0-9\-./ ]{3,40}")
_ALFANUMERICO = re.compile(r"[A-Za-z0-9]")

# phonenumbers convierte letras en dígitos (teclados alfabéticos); CA-02 exige
# rechazarlas, así que los caracteres se revisan antes de interpretar el número.
_TELEFONO = re.compile(
    r"\+?[0-9 \-().]+(?: *(?:ext\.?|extensi[oó]n|x) *[0-9]{1,6})?", re.IGNORECASE
)
# Solo la representación que emitimos: E.164 seguido de una extensión RFC 3966.
# No se admite una URI tel: completa ni parámetros arbitrarios.
_TELEFONO_CANONICO_CON_EXTENSION = re.compile(r"\+[1-9][0-9]{1,14};ext=[0-9]{1,6}")
_REGION_POR_DEFECTO = "CO"

# Separadores de presentación comunes a Python y JavaScript. Los controles
# restantes y caracteres de formato (p. ej. NEL, BOM o ancho cero) se conservan
# para rechazarlos; no deben desaparecer silenciosamente al normalizar.
_ESPACIOS_UBICACION = re.compile(
    r"[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+"
)


def recortar_espacios_formato(valor: str) -> str:
    """Recorta solo separadores aprobados, conservando caracteres inválidos."""
    return valor.strip(ESPACIOS_FORMATO)


def _colapsar_espacios(valor: str) -> str:
    return unicodedata.normalize("NFC", _ESPACIOS_FORMATO.sub(" ", recortar_espacios_formato(valor)))


def normalizar_texto_ubicacion(valor: str) -> str:
    """H-06: mismo texto canónico antes de medirlo en esquema y servicio."""
    return unicodedata.normalize("NFC", _ESPACIOS_UBICACION.sub(" ", valor).strip(" "))


def _tiene_letra(valor: str) -> bool:
    return any(unicodedata.category(caracter).startswith("L") for caracter in valor)


def _caracteres_ubicacion_validos(valor: str, signos: str, *, numeros: bool = False) -> bool:
    """Letras Unicode con marcas únicamente sobre una base de letra previa."""
    base_letra = False
    for caracter in valor:
        categoria = unicodedata.category(caracter)
        if categoria.startswith("L"):
            base_letra = True
        elif categoria.startswith("M") and base_letra:
            continue
        else:
            base_letra = False
            if caracter not in signos and not (numeros and categoria.startswith("N")):
                return False
    return True


def calcular_digito_verificacion_nit(base: str) -> int:
    suma = sum(
        int(digito) * peso
        for digito, peso in zip(reversed(base), _PESOS_DV_NIT, strict=False)
    )
    residuo = suma % 11
    return residuo if residuo < 2 else 11 - residuo


def normalizar_digito_verificacion_nit(base: str | None, valor: str) -> str:
    """El DV se registra en su propio campo y debe coincidir con el de la DIAN."""
    digito = recortar_espacios_formato(valor)
    if not _DIGITO.fullmatch(digito):
        raise ValueError("El dígito de verificación debe ser un solo dígito")
    if base and int(digito) != calcular_digito_verificacion_nit(base):
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
        cedula = _ESPACIOS_FORMATO.sub("", valor).upper()
        if not _CEDULA_EXTRANJERIA.fullmatch(cedula):
            raise ValueError(
                "La cédula de extranjería debe tener entre 3 y 15 letras o dígitos"
            )
        return cedula
    if tipo == TipoIdentificacion.PASAPORTE:
        pasaporte = _ESPACIOS_FORMATO.sub("", valor).upper()
        if not _PASAPORTE.fullmatch(pasaporte):
            raise ValueError("El pasaporte debe tener entre 5 y 20 letras o dígitos")
        return pasaporte
    identificacion = _colapsar_espacios(valor)
    if not (
        _IDENTIFICACION_LIBRE.fullmatch(identificacion)
        and _ALFANUMERICO.search(identificacion)
    ):
        raise ValueError(
            "La identificación debe tener entre 3 y 40 caracteres: letras, "
            "dígitos, espacios, guion, punto o barra; incluya al menos una letra o dígito"
        )
    return identificacion


def normalizar_telefono(valor: str) -> str:
    """CA-02 y RN-05: plan de numeración del país; sin indicativo, Colombia."""
    telefono = _ESPACIOS_FORMATO.sub(" ", recortar_espacios_formato(valor))
    mensaje = (
        "Ingrese un teléfono válido. Para números fuera de Colombia, "
        "incluya el indicativo con + (por ejemplo, +34 912 345 678)"
    )
    if not (
        _TELEFONO.fullmatch(telefono)
        or _TELEFONO_CANONICO_CON_EXTENSION.fullmatch(telefono)
    ):
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
    ciudad = normalizar_texto_ubicacion(valor)
    if not (
        2 <= len(ciudad) <= 120
        and unicodedata.category(ciudad[0]).startswith("L")
        and _caracteres_ubicacion_validos(ciudad, " -.'")
    ):
        raise ValueError(
            "La ciudad debe tener entre 2 y 120 caracteres y contener solo "
            "letras, espacios, guion, punto o apóstrofo"
        )
    return ciudad


def normalizar_direccion(valor: str) -> str:
    """CA-04: número o referencias separadas, sin verificar existencia física.

    Las referencias sin número (rurales o internacionales) pueden indicar lugar
    y localidad separados por coma o barra. No se exige vocabulario colombiano.
    Esta estructura tampoco demuestra que el texto sea una dirección real.
    """
    direccion = normalizar_texto_ubicacion(valor)
    referencias = re.split(r"[,/]", direccion)
    tiene_referencia = any(caracter.isdecimal() for caracter in direccion) or (
        len(referencias) >= 2
        and all(_tiene_letra(referencia) for referencia in referencias)
    )
    if not (
        5 <= len(direccion) <= 200
        and _caracteres_ubicacion_validos(direccion, " #-.,/°º()'", numeros=True)
        and _tiene_letra(direccion)
        and tiene_referencia
    ):
        raise ValueError(
            "La dirección debe tener entre 5 y 200 caracteres, incluir letras "
            "y un número o dos referencias separadas por coma o barra. "
            "Use solo letras, dígitos, espacios y los signos # - . , / ° º ( ) '"
        )
    return direccion


def identificacion_completa(
    tipo: str | None, base: str | None, digito_verificacion: str | None
) -> str | None:
    """Identificación para mostrar: el NIT se acompaña de su DV cuando existe."""
    if base and tipo == TipoIdentificacion.NIT and digito_verificacion:
        return f"{base}-{digito_verificacion}"
    return base


_TERMINO_NIT_CON_DV = re.compile(r"(?P<base>\d+)-\d")


def termino_busqueda_identificacion(termino: str) -> str:
    """Término para buscar en la identificación, que se guarda por su base.

    Si lo escrito parece una identificación numérica (con puntos, espacios o
    el DV del NIT), se reduce a su base; si no, se busca tal como se escribió.
    """
    original = recortar_espacios_formato(termino)
    compacto = _SEPARADORES_NUMERICOS.sub("", original)
    con_dv = _TERMINO_NIT_CON_DV.fullmatch(compacto)
    if con_dv:
        return con_dv["base"]
    return compacto if compacto.isdecimal() else original
