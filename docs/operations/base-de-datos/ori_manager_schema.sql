--
-- PostgreSQL database dump
--

\restrict orimanager

-- Dumped from database version 18.6 (Debian 18.6-1.pgdg13+2)
-- Dumped by pg_dump version 18.6 (Debian 18.6-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ori_internal; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ori_internal;


--
-- Name: conciliar_estados_ht10(date, boolean); Type: FUNCTION; Schema: ori_internal; Owner: -
--

CREATE FUNCTION ori_internal.conciliar_estados_ht10(p_fecha_referencia date DEFAULT NULL::date, p_simular boolean DEFAULT true) RETURNS jsonb
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
DECLARE
    v_hoy date := COALESCE(
        p_fecha_referencia,
        (clock_timestamp() AT TIME ZONE 'America/Bogota')::date
    );
    v_cambio text;
    v_cambios integer := 0;
    v_sin_fecha integer := 0;
    v_legado_inconsistente integer := 0;
    v_transiciones jsonb := '[]'::jsonb;
    r record;
BEGIN
    -- No permitir NULL para que una omisión nunca derive en escritura.
    IF p_simular IS NULL THEN
        RAISE EXCEPTION 'HT-10: p_simular debe ser true o false';
    END IF;

    -- Una fecha de prueba no puede provocar cambios reales en Staging/Producción.
    -- El CLI original conserva sus propias defensas para pruebas locales.
    IF p_fecha_referencia IS NOT NULL AND NOT p_simular THEN
        RAISE EXCEPTION 'HT-10: las ejecuciones reales deben utilizar la fecha actual de Bogotá';
    END IF;

    -- Bloquear en orden fijo evita omisiones silenciosas y reduce interbloqueos.
    -- La transacción que invoca la función incluye updates + ambas auditorías.
    FOR r IN
        SELECT c.id, c.estado, c.fecha_vencimiento
        FROM public.convenio AS c
        WHERE c.estado IN ('VIGENTE', 'POR_VENCER', 'VENCIDO')
        ORDER BY c.id
        FOR UPDATE OF c
    LOOP
        IF r.fecha_vencimiento IS NULL THEN
            v_sin_fecha := v_sin_fecha + 1;
            CONTINUE;
        END IF;

        IF r.estado = 'VENCIDO' AND r.fecha_vencimiento >= v_hoy THEN
            v_legado_inconsistente := v_legado_inconsistente + 1;
            CONTINUE;
        END IF;

        v_cambio := CASE
            WHEN r.fecha_vencimiento < v_hoy THEN 'FINALIZADO'
            WHEN r.fecha_vencimiento <= v_hoy + 120 THEN 'POR_VENCER'
            ELSE 'VIGENTE'
        END;

        IF v_cambio = r.estado THEN
            CONTINUE;
        END IF;

        v_cambios := v_cambios + 1;
        v_transiciones := v_transiciones || jsonb_build_array(
            jsonb_build_object(
                'convenio_id', r.id,
                'anterior', r.estado,
                'nuevo', v_cambio
            )
        );

        IF p_simular THEN
            CONTINUE;
        END IF;

        UPDATE public.convenio AS c
        SET estado = v_cambio,
            actualizado_en = clock_timestamp()
        WHERE c.id = r.id AND c.estado = r.estado;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'HT-10: actualización concurrente inesperada para convenio %', r.id;
        END IF;

        INSERT INTO public.transicion_estado_convenio (
            convenio_id, estado_anterior, estado_nuevo,
            fecha_referencia, fecha_vencimiento
        ) VALUES (
            r.id, r.estado, v_cambio, v_hoy, r.fecha_vencimiento
        );

        -- La auditoría SQL debe reproducir el contrato HT-09; los eventos de
        -- SQL no pasan por el hook after_flush() del ORM de SQLAlchemy.
        INSERT INTO public.auditoria (
            usuario_id, rol, entidad, registro_id, accion, campo,
            valor_anterior, valor_nuevo, contexto, evento, ejecucion
        ) VALUES (
            NULL, NULL, 'convenio', r.id, 'UPDATE', 'estado',
            r.estado, v_cambio,
            'Concilió automáticamente el estado contractual de los convenios',
            'CONCILIACION_ESTADO_AUTOMATICA', 'AUTOMATICA'
        );
    END LOOP;

    RETURN jsonb_build_object(
        'fecha_referencia', v_hoy,
        'simulado', p_simular,
        'cambios', v_cambios,
        'sin_fecha', v_sin_fecha,
        'legado_inconsistente', v_legado_inconsistente,
        'transiciones', v_transiciones
    );
END;
$$;


--
-- Name: auditoria_completar_rol(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auditoria_completar_rol() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.rol IS NULL THEN
                SELECT r.codigo INTO NEW.rol
                FROM usuario AS u
                JOIN rol AS r ON r.id = u.rol_id
                WHERE u.id = NEW.usuario_id;
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: auditoria_no_sobrescribible(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auditoria_no_sobrescribible() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'La bitácora de auditoría no admite modificar registros';
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: actividad_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actividad_convenio (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    titulo character varying(200) NOT NULL,
    descripcion text NOT NULL,
    tipo character varying(80),
    parte_ejecutora character varying(20),
    fecha_planificada date,
    fecha_ejecucion date,
    estado character varying(20) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    resultado text,
    observaciones text,
    numero_participantes smallint,
    responsable_nombre character varying(200),
    responsable_id integer,
    registrado_por_id integer NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_actividad_convenio_estado CHECK (((estado)::text = ANY ((ARRAY['PENDIENTE'::character varying, 'EN_CURSO'::character varying, 'REALIZADA'::character varying, 'CANCELADA'::character varying])::text[]))),
    CONSTRAINT ck_actividad_convenio_parte_ejecutora CHECK (((parte_ejecutora IS NULL) OR ((parte_ejecutora)::text = ANY ((ARRAY['USB'::character varying, 'CONTRAPARTE'::character varying, 'AMBAS'::character varying])::text[])))),
    CONSTRAINT ck_actividad_convenio_participantes_no_negativo CHECK (((numero_participantes IS NULL) OR (numero_participantes >= 0))),
    CONSTRAINT ck_actividad_convenio_realizada_requiere_fecha_ejecucion CHECK ((((estado)::text <> 'REALIZADA'::text) OR (fecha_ejecucion IS NOT NULL)))
);


--
-- Name: actividad_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.actividad_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: actividad_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.actividad_convenio_id_seq OWNED BY public.actividad_convenio.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: aliado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aliado (
    id integer NOT NULL,
    nombre character varying(200) NOT NULL,
    tipo character varying(22) NOT NULL,
    sector_economico character varying(120),
    identificacion character varying(40) NOT NULL,
    pais_id integer,
    ciudad character varying(120),
    direccion character varying(200),
    telefono character varying(40),
    correo character varying(160),
    sitio_web character varying(200),
    activo boolean DEFAULT true NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    tipo_identificacion character varying(33) NOT NULL,
    digito_verificacion character varying(1),
    CONSTRAINT ck_aliado_digito_verificacion CHECK (((digito_verificacion IS NULL) OR (((tipo_identificacion)::text = 'NIT'::text) AND ((digito_verificacion)::text ~ '^[0-9]$'::text)))),
    CONSTRAINT ck_aliado_empresa_sector_economico CHECK ((((tipo)::text <> 'EMPRESA'::text) OR ((sector_economico IS NOT NULL) AND (btrim((sector_economico)::text) <> ''::text)))),
    CONSTRAINT ck_aliado_tipo CHECK (((tipo)::text = ANY ((ARRAY['UNIVERSIDAD'::character varying, 'COLEGIO'::character varying, 'EMPRESA'::character varying, 'ENTIDAD_GUBERNAMENTAL'::character varying])::text[]))),
    CONSTRAINT ck_aliado_tipo_identificacion CHECK (((tipo_identificacion)::text = ANY ((ARRAY['NIT'::character varying, 'CEDULA_CIUDADANIA'::character varying, 'CEDULA_EXTRANJERIA'::character varying, 'PASAPORTE'::character varying, 'IDENTIFICACION_FISCAL_EXTRANJERA'::character varying, 'OTRO'::character varying])::text[])))
);


--
-- Name: aliado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.aliado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: aliado_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.aliado_id_seq OWNED BY public.aliado.id;


--
-- Name: auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auditoria (
    id bigint NOT NULL,
    usuario_id integer,
    entidad character varying(80) NOT NULL,
    registro_id integer NOT NULL,
    accion character varying(10) NOT NULL,
    campo character varying(80),
    valor_anterior text,
    valor_nuevo text,
    direccion_ip character varying(45),
    fecha_hora timestamp with time zone DEFAULT now() NOT NULL,
    rol character varying(40),
    contexto text,
    evento character varying(40),
    etapa character varying(40),
    version integer,
    ejecucion character varying(20),
    responsable_id integer,
    CONSTRAINT ck_auditoria_accion CHECK (((accion)::text = ANY ((ARRAY['INSERT'::character varying, 'UPDATE'::character varying, 'DELETE'::character varying])::text[]))),
    CONSTRAINT ck_auditoria_ejecucion CHECK (((ejecucion IS NULL) OR ((ejecucion)::text = ANY ((ARRAY['HUMANA'::character varying, 'AUTOMATICA'::character varying])::text[])))),
    CONSTRAINT ck_auditoria_usuario_o_automatica CHECK (((usuario_id IS NOT NULL) OR (NOT ((ejecucion)::text IS DISTINCT FROM 'AUTOMATICA'::text))))
);


--
-- Name: auditoria_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auditoria_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auditoria_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auditoria_id_seq OWNED BY public.auditoria.id;


--
-- Name: borrador_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.borrador_convenio (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    contenido jsonb NOT NULL,
    revision integer NOT NULL,
    actualizado_por_id integer NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_borrador_convenio_revision_positiva CHECK ((revision > 0))
);


--
-- Name: borrador_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.borrador_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: borrador_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.borrador_convenio_id_seq OWNED BY public.borrador_convenio.id;


--
-- Name: contacto_aliado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contacto_aliado (
    id integer NOT NULL,
    aliado_id integer NOT NULL,
    nombre character varying(160) NOT NULL,
    cargo character varying(120),
    correo character varying(160),
    telefono character varying(40),
    extension character varying(20),
    es_principal boolean DEFAULT false NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: contacto_aliado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contacto_aliado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contacto_aliado_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contacto_aliado_id_seq OWNED BY public.contacto_aliado.id;


--
-- Name: contador_codigo_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contador_codigo_convenio (
    anio integer NOT NULL,
    ultimo_consecutivo integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_contador_codigo_convenio_consecutivo CHECK ((ultimo_consecutivo >= 0))
);


--
-- Name: convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.convenio (
    id integer NOT NULL,
    codigo character varying(40),
    solicitud_id integer,
    aliado_id integer,
    tipo_convenio_id integer,
    etapa_actual_id integer,
    estado character varying(20) DEFAULT 'EN_TRAMITE'::character varying NOT NULL,
    objeto text,
    alcance character varying(20),
    unidad_organizacional_id integer,
    implicacion_financiera text,
    fecha_inicio date,
    fecha_vencimiento date,
    fecha_firma date,
    duracion_meses integer,
    porcentaje_avance smallint,
    convenio_origen_id integer,
    numero_renovacion smallint,
    creado_por_id integer NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    plantilla_origen_id integer,
    version_actual integer DEFAULT 0 NOT NULL,
    origen character varying(20) DEFAULT 'SOLICITUD'::character varying NOT NULL,
    elaboracion_iniciada_en timestamp with time zone,
    activado_en timestamp with time zone,
    vigencia_ht17 boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_convenio_alcance CHECK (((alcance IS NULL) OR ((alcance)::text = ANY ((ARRAY['PROGRAMA'::character varying, 'INSTITUCIONAL'::character varying])::text[])))),
    CONSTRAINT ck_convenio_estado CHECK (((estado)::text = ANY ((ARRAY['EN_TRAMITE'::character varying, 'VIGENTE'::character varying, 'POR_VENCER'::character varying, 'VENCIDO'::character varying, 'RENOVADO'::character varying, 'FINALIZADO'::character varying, 'CANCELADO'::character varying])::text[]))),
    CONSTRAINT ck_convenio_origen CHECK (((origen)::text = ANY ((ARRAY['SOLICITUD'::character varying, 'MANUAL_ORI'::character varying])::text[]))),
    CONSTRAINT ck_convenio_origen_solicitud CHECK (((((origen)::text = 'SOLICITUD'::text) AND (solicitud_id IS NOT NULL)) OR (((origen)::text = 'MANUAL_ORI'::text) AND (solicitud_id IS NULL)))),
    CONSTRAINT ck_convenio_porcentaje_avance CHECK (((porcentaje_avance IS NULL) OR ((porcentaje_avance >= 0) AND (porcentaje_avance <= 100)))),
    CONSTRAINT ck_convenio_version_actual_no_negativa CHECK ((version_actual >= 0))
);


--
-- Name: convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.convenio_id_seq OWNED BY public.convenio.id;


--
-- Name: decision_no_renovacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.decision_no_renovacion (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    fecha_vencimiento_origen date NOT NULL,
    decidida_por_id integer NOT NULL,
    decidida_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: decision_no_renovacion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.decision_no_renovacion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: decision_no_renovacion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.decision_no_renovacion_id_seq OWNED BY public.decision_no_renovacion.id;


--
-- Name: documento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documento (
    id integer CONSTRAINT documento_solicitud_id_not_null NOT NULL,
    solicitud_id integer,
    tipo character varying(40) CONSTRAINT documento_solicitud_tipo_documento_not_null NOT NULL,
    nombre_archivo character varying(255) CONSTRAINT documento_solicitud_nombre_original_not_null NOT NULL,
    tipo_mime character varying(120) CONSTRAINT documento_solicitud_tipo_mime_not_null NOT NULL,
    tamano_bytes bigint CONSTRAINT documento_solicitud_tamano_bytes_not_null NOT NULL,
    ruta_almacenamiento character varying(500) CONSTRAINT documento_solicitud_clave_objeto_not_null NOT NULL,
    creado_en timestamp with time zone DEFAULT now() CONSTRAINT documento_solicitud_creado_en_not_null NOT NULL,
    convenio_id integer,
    version smallint,
    es_vigente boolean DEFAULT true NOT NULL,
    cargado_por_id integer,
    CONSTRAINT ck_documento_solicitud_o_convenio CHECK (((solicitud_id IS NOT NULL) OR (convenio_id IS NOT NULL))),
    CONSTRAINT ck_documento_tamano CHECK ((tamano_bytes > 0)),
    CONSTRAINT ck_documento_tipo CHECK (((tipo)::text = ANY ((ARRAY['CAMARA_COMERCIO'::character varying, 'RUT'::character varying, 'CEDULA_REPRESENTANTE_LEGAL'::character varying, 'OTRO_DOCUMENTO_REPRESENTACION'::character varying, 'OTRO_SOPORTE'::character varying, 'FORMATO_SOLICITUD'::character varying, 'CEDULA_REPRESENTANTE'::character varying, 'BORRADOR'::character varying, 'AVAL_JURIDICO'::character varying, 'CONVENIO_FIRMADO'::character varying, 'OTROSI'::character varying, 'ACTA_TERMINACION'::character varying, 'SOPORTE'::character varying])::text[])))
);


--
-- Name: documento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documento_id_seq OWNED BY public.documento.id;


--
-- Name: estado_guia_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.estado_guia_usuario (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    guia character varying(40) NOT NULL,
    version integer NOT NULL,
    estado character varying(20) NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_estado_guia_usuario_estado CHECK (((estado)::text = ANY ((ARRAY['COMPLETADO'::character varying, 'OMITIDO'::character varying])::text[]))),
    CONSTRAINT ck_estado_guia_usuario_guia CHECK (((guia)::text = ANY ((ARRAY['ONBOARDING_INICIAL'::character varying, 'GUIA_RADICACION'::character varying])::text[]))),
    CONSTRAINT ck_estado_guia_usuario_version CHECK ((version >= 1))
);


--
-- Name: estado_guia_usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.estado_guia_usuario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: estado_guia_usuario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.estado_guia_usuario_id_seq OWNED BY public.estado_guia_usuario.id;


--
-- Name: etapa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.etapa (
    id integer NOT NULL,
    orden smallint NOT NULL,
    codigo character varying(60) NOT NULL,
    nombre character varying(120) NOT NULL,
    descripcion text,
    area_responsable character varying(120),
    activa boolean DEFAULT true NOT NULL
);


--
-- Name: etapa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.etapa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: etapa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.etapa_id_seq OWNED BY public.etapa.id;


--
-- Name: evaluacion_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluacion_convenio (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    evaluado_por_id integer NOT NULL,
    fue_funcional boolean NOT NULL,
    calificacion smallint NOT NULL,
    observaciones text NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_evaluacion_convenio_calificacion CHECK (((calificacion >= 1) AND (calificacion <= 10)))
);


--
-- Name: evaluacion_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.evaluacion_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: evaluacion_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.evaluacion_convenio_id_seq OWNED BY public.evaluacion_convenio.id;


--
-- Name: firma_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.firma_convenio (
    id integer NOT NULL,
    proceso_firmas_id integer NOT NULL,
    orden smallint NOT NULL,
    rol_firmante character varying(40) NOT NULL,
    parte character varying(40) NOT NULL,
    usuario_id integer,
    nombre_firmante character varying(160),
    cargo_firmante character varying(160),
    correo_firmante character varying(320),
    modalidad character varying(20),
    estado character varying(20) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    fecha_firma timestamp with time zone,
    documento_id integer,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    firma_png bytea,
    firma_sha256 character varying(64),
    CONSTRAINT ck_firma_convenio_electronica_correo CHECK ((((modalidad)::text <> 'ELECTRONICA'::text) OR (correo_firmante IS NOT NULL))),
    CONSTRAINT ck_firma_convenio_estado CHECK (((estado)::text = ANY ((ARRAY['PENDIENTE'::character varying, 'FIRMADA'::character varying])::text[]))),
    CONSTRAINT ck_firma_convenio_evidencia_electronica_completa CHECK ((((firma_png IS NULL) AND (firma_sha256 IS NULL)) OR ((firma_png IS NOT NULL) AND (firma_sha256 IS NOT NULL)))),
    CONSTRAINT ck_firma_convenio_modalidad CHECK (((modalidad IS NULL) OR ((modalidad)::text = ANY ((ARRAY['ELECTRONICA'::character varying, 'FISICA'::character varying])::text[])))),
    CONSTRAINT ck_firma_convenio_orden CHECK (((orden >= 1) AND (orden <= 7))),
    CONSTRAINT ck_firma_convenio_parte CHECK (((parte)::text = ANY ((ARRAY['UNIVERSIDAD'::character varying, 'UNIDAD_SOLICITANTE'::character varying, 'REPRESENTANTE_LEGAL_ENTIDAD'::character varying])::text[]))),
    CONSTRAINT ck_firma_convenio_rol CHECK (((rol_firmante)::text = ANY ((ARRAY['ADMINISTRADOR_ORI'::character varying, 'REVISOR_ORI'::character varying, 'VICERRECTORIA_FINANCIERA'::character varying, 'VICERRECTORIA_ACADEMICA'::character varying, 'SECRETARIA'::character varying, 'RECTOR'::character varying, 'PARTE_SOLICITANTE'::character varying])::text[])))
);


--
-- Name: firma_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.firma_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: firma_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.firma_convenio_id_seq OWNED BY public.firma_convenio.id;


--
-- Name: historial_etapa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historial_etapa (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    etapa_origen_id integer,
    etapa_destino_id integer NOT NULL,
    usuario_id integer NOT NULL,
    responsable_id integer,
    observacion text,
    fecha_cambio timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: historial_etapa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.historial_etapa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: historial_etapa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.historial_etapa_id_seq OWNED BY public.historial_etapa.id;


--
-- Name: invitacion_firma_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invitacion_firma_convenio (
    id integer NOT NULL,
    firma_convenio_id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    expira_en timestamp with time zone NOT NULL,
    enviado_en timestamp with time zone,
    utilizado_en timestamp with time zone,
    revocado_en timestamp with time zone,
    generada_por_id integer NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: invitacion_firma_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invitacion_firma_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invitacion_firma_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invitacion_firma_convenio_id_seq OWNED BY public.invitacion_firma_convenio.id;


--
-- Name: invitacion_revision_contraparte; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invitacion_revision_contraparte (
    id integer NOT NULL,
    revision_convenio_id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    correo_destino character varying(320) NOT NULL,
    correo_cc character varying(320),
    expira_en timestamp with time zone NOT NULL,
    enviado_en timestamp with time zone,
    utilizado_en timestamp with time zone,
    revocado_en timestamp with time zone,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    generada_por_id integer NOT NULL
);


--
-- Name: invitacion_revision_contraparte_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invitacion_revision_contraparte_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invitacion_revision_contraparte_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invitacion_revision_contraparte_id_seq OWNED BY public.invitacion_revision_contraparte.id;


--
-- Name: notificacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notificacion (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    tipo character varying(40) NOT NULL,
    entidad_tipo character varying(20) NOT NULL,
    entidad_id integer NOT NULL,
    mensaje text NOT NULL,
    leida boolean DEFAULT false NOT NULL,
    leida_en timestamp with time zone,
    resuelta boolean DEFAULT false NOT NULL,
    resuelta_en timestamp with time zone,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_notificacion_entidad_tipo CHECK (((entidad_tipo)::text = ANY ((ARRAY['CONVENIO'::character varying, 'SOLICITUD'::character varying])::text[]))),
    CONSTRAINT ck_notificacion_tipo CHECK (((tipo)::text = ANY ((ARRAY['REVISION_JURIDICA_PENDIENTE'::character varying, 'DEVOLUCION_REVISION'::character varying, 'SOLICITUD_DEVUELTA'::character varying, 'REVISION_CONTRAPARTE_PENDIENTE'::character varying])::text[])))
);


--
-- Name: notificacion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notificacion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notificacion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notificacion_id_seq OWNED BY public.notificacion.id;


--
-- Name: observacion_revision; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.observacion_revision (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    historial_etapa_id integer NOT NULL,
    origen character varying(30) NOT NULL,
    registrada_por_id integer,
    responsable_id integer,
    descripcion text NOT NULL,
    respuesta text,
    atendida_por_id integer,
    fecha_atencion timestamp with time zone,
    estado character varying(20) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    revision_convenio_id integer,
    requiere_correccion boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_observacion_revision_actor_registrado CHECK ((((origen)::text = 'CONTRAPARTE'::text) OR (registrada_por_id IS NOT NULL))),
    CONSTRAINT ck_observacion_revision_estado CHECK (((estado)::text = ANY ((ARRAY['PENDIENTE'::character varying, 'ATENDIDA'::character varying])::text[]))),
    CONSTRAINT ck_observacion_revision_origen CHECK (((origen)::text = ANY ((ARRAY['REVISOR_ORI'::character varying, 'CONTRAPARTE'::character varying, 'REVISION_FINAL_ORI'::character varying])::text[])))
);


--
-- Name: observacion_revision_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.observacion_revision_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: observacion_revision_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.observacion_revision_id_seq OWNED BY public.observacion_revision.id;


--
-- Name: pais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pais (
    id integer NOT NULL,
    codigo_iso character(2) NOT NULL,
    nombre character varying(80) NOT NULL
);


--
-- Name: pais_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pais_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pais_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pais_id_seq OWNED BY public.pais.id;


--
-- Name: plantilla_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plantilla_convenio (
    id integer NOT NULL,
    codigo character varying(60) NOT NULL,
    nombre character varying(160) NOT NULL,
    contenido_base jsonb NOT NULL,
    activa boolean DEFAULT true NOT NULL,
    creado_por_id integer,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: plantilla_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.plantilla_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: plantilla_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.plantilla_convenio_id_seq OWNED BY public.plantilla_convenio.id;


--
-- Name: proceso_firmas_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proceso_firmas_convenio (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    version_convenio_id integer NOT NULL,
    revision_final_id integer NOT NULL,
    creado_por_id integer NOT NULL,
    estado character varying(20) DEFAULT 'CONFIGURACION'::character varying NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    iniciado_en timestamp with time zone,
    completado_en timestamp with time zone,
    cancelado_en timestamp with time zone,
    CONSTRAINT ck_proceso_firmas_convenio_estado CHECK (((estado)::text = ANY ((ARRAY['CONFIGURACION'::character varying, 'EN_CURSO'::character varying, 'COMPLETADO'::character varying, 'CANCELADO'::character varying])::text[])))
);


--
-- Name: proceso_firmas_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proceso_firmas_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proceso_firmas_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proceso_firmas_convenio_id_seq OWNED BY public.proceso_firmas_convenio.id;


--
-- Name: respuesta_revision_contraparte; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.respuesta_revision_contraparte (
    id integer NOT NULL,
    revision_convenio_id integer NOT NULL,
    nombre_firmante character varying(160) NOT NULL,
    cargo_firmante character varying(160) NOT NULL,
    correo_actor character varying(320) NOT NULL,
    firma_png bytea,
    firma_sha256 character varying(64),
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: respuesta_revision_contraparte_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.respuesta_revision_contraparte_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: respuesta_revision_contraparte_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.respuesta_revision_contraparte_id_seq OWNED BY public.respuesta_revision_contraparte.id;


--
-- Name: revision_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.revision_convenio (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    tipo character varying(20) NOT NULL,
    historial_etapa_id integer,
    documento_id integer,
    responsable_id integer,
    estado character varying(20) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    resultado character varying(20),
    resuelta_por_id integer,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    resuelta_en timestamp with time zone,
    snapshot_datos jsonb,
    version_convenio_id integer,
    instancia_juridica smallint,
    numero_ronda integer,
    version_resultado_id integer,
    creada_por_id integer,
    CONSTRAINT ck_revision_convenio_coordenadas_juridicas CHECK (((instancia_juridica IS NULL) = (numero_ronda IS NULL))),
    CONSTRAINT ck_revision_convenio_estado CHECK (((estado)::text = ANY ((ARRAY['PENDIENTE'::character varying, 'RESUELTA'::character varying])::text[]))),
    CONSTRAINT ck_revision_convenio_instancia_juridica CHECK (((instancia_juridica IS NULL) OR (instancia_juridica = ANY (ARRAY[1, 2])))),
    CONSTRAINT ck_revision_convenio_numero_ronda_positivo CHECK (((numero_ronda IS NULL) OR (numero_ronda > 0))),
    CONSTRAINT ck_revision_convenio_resultado CHECK (((resultado IS NULL) OR ((resultado)::text = ANY ((ARRAY['APROBADA'::character varying, 'DEVUELTA'::character varying])::text[])))),
    CONSTRAINT ck_revision_convenio_tipo CHECK (((tipo)::text = ANY ((ARRAY['JURIDICA'::character varying, 'CONTRAPARTE'::character varying, 'FINAL'::character varying])::text[])))
);


--
-- Name: revision_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.revision_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: revision_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.revision_convenio_id_seq OWNED BY public.revision_convenio.id;


--
-- Name: rol; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rol (
    id integer NOT NULL,
    codigo character varying(40) NOT NULL,
    nombre character varying(80) NOT NULL,
    descripcion text,
    es_interno boolean DEFAULT true NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rol_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rol_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rol_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rol_id_seq OWNED BY public.rol.id;


--
-- Name: solicitud_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitud_convenio (
    id integer NOT NULL,
    consecutivo character varying(40) NOT NULL,
    tipo_solicitante character varying(7) NOT NULL,
    solicitante_id integer NOT NULL,
    unidad_organizacional_id integer,
    aliado_id integer,
    nombre_aliado_propuesto character varying(200),
    tipo_convenio_id integer,
    objeto text,
    justificacion text,
    actividades_por_parte text,
    metas_esperadas text,
    implicacion_financiera text,
    vigencia_estimada character varying(120),
    requisitos_renovacion text,
    observaciones text,
    aprobada_por_director boolean DEFAULT false NOT NULL,
    fecha_aprobacion_director date,
    fecha_radicacion timestamp with time zone,
    fecha_recibido_ori timestamp with time zone,
    estado character varying(20) DEFAULT 'BORRADOR'::character varying NOT NULL,
    motivo_rechazo text,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    tipo_identificacion_aliado_propuesto character varying(33),
    identificacion_aliado_propuesto character varying(40),
    tipo_aliado_propuesto character varying(22),
    correo_aliado_propuesto character varying(160),
    sector_economico_aliado_propuesto character varying(120),
    contacto_contraparte_nombre character varying(160),
    contacto_contraparte_cargo character varying(120),
    contacto_contraparte_telefono character varying(40),
    contacto_contraparte_correo character varying(160),
    pais_aliado_propuesto character varying(80),
    ciudad_aliado_propuesto character varying(120),
    telefono_aliado_propuesto character varying(40),
    direccion_aliado_propuesto character varying(200),
    supervisor_usb_nombre character varying(160),
    supervisor_usb_cargo character varying(120),
    supervisor_usb_telefono character varying(40),
    supervisor_usb_correo character varying(160),
    supervisor_contraparte_nombre character varying(160),
    supervisor_contraparte_cargo character varying(120),
    supervisor_contraparte_telefono character varying(40),
    supervisor_contraparte_correo character varying(160),
    solicitante_nombre character varying(160),
    solicitante_correo character varying(160),
    solicitante_documento character varying(40),
    solicitante_cargo character varying(120),
    solicitante_entidad character varying(160),
    solicitante_unidad character varying(160),
    solicitante_programa character varying(160),
    observaciones_devolucion text,
    decidida_por_id integer,
    fecha_decision timestamp with time zone,
    solicitante_tipo_documento character varying(33),
    digito_verificacion_aliado_propuesto character varying(1),
    solicitante_digito_verificacion character varying(1),
    pais_aliado_propuesto_id integer,
    CONSTRAINT ck_solicitud_digito_verificacion_aliado_propuesto CHECK (((digito_verificacion_aliado_propuesto IS NULL) OR (((tipo_identificacion_aliado_propuesto)::text = 'NIT'::text) AND ((digito_verificacion_aliado_propuesto)::text ~ '^[0-9]$'::text)))),
    CONSTRAINT ck_solicitud_estado CHECK (((estado)::text = ANY ((ARRAY['BORRADOR'::character varying, 'RADICADA'::character varying, 'EN_ESTUDIO'::character varying, 'DEVUELTA'::character varying, 'APROBADA'::character varying, 'RECHAZADA'::character varying])::text[]))),
    CONSTRAINT ck_solicitud_solicitante_digito_verificacion CHECK (((solicitante_digito_verificacion IS NULL) OR (((solicitante_tipo_documento)::text = 'NIT'::text) AND ((solicitante_digito_verificacion)::text ~ '^[0-9]$'::text)))),
    CONSTRAINT ck_solicitud_solicitante_tipo_documento CHECK (((solicitante_tipo_documento)::text = ANY ((ARRAY['NIT'::character varying, 'CEDULA_CIUDADANIA'::character varying, 'CEDULA_EXTRANJERIA'::character varying, 'PASAPORTE'::character varying, 'IDENTIFICACION_FISCAL_EXTRANJERA'::character varying, 'OTRO'::character varying])::text[]))),
    CONSTRAINT ck_solicitud_tipo_aliado_propuesto CHECK (((tipo_aliado_propuesto)::text = ANY ((ARRAY['UNIVERSIDAD'::character varying, 'COLEGIO'::character varying, 'EMPRESA'::character varying, 'ENTIDAD_GUBERNAMENTAL'::character varying])::text[]))),
    CONSTRAINT ck_solicitud_tipo_identificacion_aliado_propuesto CHECK (((tipo_identificacion_aliado_propuesto)::text = ANY ((ARRAY['NIT'::character varying, 'CEDULA_CIUDADANIA'::character varying, 'CEDULA_EXTRANJERIA'::character varying, 'PASAPORTE'::character varying, 'IDENTIFICACION_FISCAL_EXTRANJERA'::character varying, 'OTRO'::character varying])::text[]))),
    CONSTRAINT ck_solicitud_tipo_solicitante CHECK (((tipo_solicitante)::text = ANY ((ARRAY['INTERNO'::character varying, 'EXTERNO'::character varying])::text[])))
);


--
-- Name: solicitud_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitud_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitud_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitud_convenio_id_seq OWNED BY public.solicitud_convenio.id;


--
-- Name: solicitud_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitud_usuario (
    id integer NOT NULL,
    solicitud_id integer NOT NULL,
    usuario_id integer NOT NULL
);


--
-- Name: solicitud_usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitud_usuario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitud_usuario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitud_usuario_id_seq OWNED BY public.solicitud_usuario.id;


--
-- Name: solicitud_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitud_version (
    id integer NOT NULL,
    solicitud_id integer NOT NULL,
    numero integer NOT NULL,
    datos jsonb NOT NULL,
    radicada_por_id integer NOT NULL,
    radicada_en timestamp with time zone NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    observaciones_devolucion text,
    devuelta_por_id integer,
    devuelta_en timestamp with time zone,
    CONSTRAINT ck_solicitud_version_devolucion_completa CHECK ((((devuelta_en IS NULL) AND (devuelta_por_id IS NULL) AND (observaciones_devolucion IS NULL)) OR ((devuelta_en IS NOT NULL) AND (devuelta_por_id IS NOT NULL) AND (observaciones_devolucion IS NOT NULL)))),
    CONSTRAINT ck_solicitud_version_numero CHECK ((numero > 0))
);


--
-- Name: solicitud_version_documento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitud_version_documento (
    solicitud_version_id integer NOT NULL,
    documento_id integer NOT NULL
);


--
-- Name: solicitud_version_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitud_version_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitud_version_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitud_version_id_seq OWNED BY public.solicitud_version.id;


--
-- Name: tipo_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tipo_convenio (
    id integer NOT NULL,
    codigo character varying(40) NOT NULL,
    nombre character varying(120) NOT NULL,
    naturaleza character varying(10),
    duracion_meses_defecto smallint,
    descripcion text,
    activo boolean DEFAULT true NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tipo_convenio_naturaleza CHECK (((naturaleza)::text = ANY ((ARRAY['MARCO'::character varying, 'ESPECIFICO'::character varying])::text[])))
);


--
-- Name: tipo_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tipo_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipo_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tipo_convenio_id_seq OWNED BY public.tipo_convenio.id;


--
-- Name: token_credencial; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_credencial (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    tipo character varying(40) NOT NULL,
    token_hash character varying(64) NOT NULL,
    expira_en timestamp with time zone NOT NULL,
    utilizado_en timestamp with time zone,
    invalidado_en timestamp with time zone,
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: token_credencial_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.token_credencial_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: token_credencial_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.token_credencial_id_seq OWNED BY public.token_credencial.id;


--
-- Name: transicion_estado_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transicion_estado_convenio (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    actor character varying(20) DEFAULT 'SISTEMA'::character varying NOT NULL,
    estado_anterior character varying(20) NOT NULL,
    estado_nuevo character varying(20) NOT NULL,
    fecha_referencia date NOT NULL,
    fecha_vencimiento date NOT NULL,
    ejecutado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_transicion_convenio_actor CHECK (((actor)::text = 'SISTEMA'::text)),
    CONSTRAINT ck_transicion_convenio_cambio CHECK (((estado_anterior)::text <> (estado_nuevo)::text))
);


--
-- Name: transicion_estado_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transicion_estado_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transicion_estado_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transicion_estado_convenio_id_seq OWNED BY public.transicion_estado_convenio.id;


--
-- Name: unidad_organizacional; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unidad_organizacional (
    id integer NOT NULL,
    codigo character varying(40) NOT NULL,
    nombre character varying(160) NOT NULL,
    tipo character varying(21) NOT NULL,
    unidad_padre_id integer,
    activa boolean DEFAULT true NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_unidad_organizacional_tipo CHECK (((tipo)::text = ANY ((ARRAY['FACULTAD'::character varying, 'PROGRAMA'::character varying, 'UNIDAD_ADMINISTRATIVA'::character varying])::text[])))
);


--
-- Name: unidad_organizacional_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unidad_organizacional_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unidad_organizacional_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unidad_organizacional_id_seq OWNED BY public.unidad_organizacional.id;


--
-- Name: usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario (
    id integer NOT NULL,
    correo character varying(160) NOT NULL,
    hash_contrasena character varying(255) NOT NULL,
    nombre_completo character varying(160) NOT NULL,
    documento_identidad character varying(40),
    telefono character varying(40),
    cargo character varying(120),
    rol_id integer NOT NULL,
    tipo_usuario character varying(7) NOT NULL,
    unidad_organizacional_id integer,
    entidad_externa character varying(160),
    activo boolean DEFAULT true NOT NULL,
    ultimo_acceso timestamp with time zone,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    actualizado_en timestamp with time zone DEFAULT now() NOT NULL,
    correo_verificado_en timestamp with time zone,
    CONSTRAINT ck_usuario_tipo_usuario CHECK (((tipo_usuario)::text = ANY ((ARRAY['INTERNO'::character varying, 'EXTERNO'::character varying])::text[])))
);


--
-- Name: usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuario_id_seq OWNED BY public.usuario.id;


--
-- Name: version_convenio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.version_convenio (
    id integer NOT NULL,
    convenio_id integer NOT NULL,
    numero integer NOT NULL,
    contenido jsonb NOT NULL,
    snapshot_metadata jsonb NOT NULL,
    autor_id integer NOT NULL,
    etapa_id integer NOT NULL,
    contexto character varying(30) NOT NULL,
    plantilla_id integer,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_version_convenio_contexto CHECK (((contexto)::text = ANY ((ARRAY['INICIALIZACION'::character varying, 'GUARDADO'::character varying, 'FINALIZACION'::character varying, 'CORRECCION_REVISION'::character varying])::text[]))),
    CONSTRAINT ck_version_convenio_numero_positivo CHECK ((numero > 0))
);


--
-- Name: version_convenio_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.version_convenio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: version_convenio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.version_convenio_id_seq OWNED BY public.version_convenio.id;


--
-- Name: actividad_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_convenio ALTER COLUMN id SET DEFAULT nextval('public.actividad_convenio_id_seq'::regclass);


--
-- Name: aliado id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aliado ALTER COLUMN id SET DEFAULT nextval('public.aliado_id_seq'::regclass);


--
-- Name: auditoria id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria ALTER COLUMN id SET DEFAULT nextval('public.auditoria_id_seq'::regclass);


--
-- Name: borrador_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.borrador_convenio ALTER COLUMN id SET DEFAULT nextval('public.borrador_convenio_id_seq'::regclass);


--
-- Name: contacto_aliado id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacto_aliado ALTER COLUMN id SET DEFAULT nextval('public.contacto_aliado_id_seq'::regclass);


--
-- Name: convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio ALTER COLUMN id SET DEFAULT nextval('public.convenio_id_seq'::regclass);


--
-- Name: decision_no_renovacion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decision_no_renovacion ALTER COLUMN id SET DEFAULT nextval('public.decision_no_renovacion_id_seq'::regclass);


--
-- Name: documento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento ALTER COLUMN id SET DEFAULT nextval('public.documento_id_seq'::regclass);


--
-- Name: estado_guia_usuario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_guia_usuario ALTER COLUMN id SET DEFAULT nextval('public.estado_guia_usuario_id_seq'::regclass);


--
-- Name: etapa id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etapa ALTER COLUMN id SET DEFAULT nextval('public.etapa_id_seq'::regclass);


--
-- Name: evaluacion_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluacion_convenio ALTER COLUMN id SET DEFAULT nextval('public.evaluacion_convenio_id_seq'::regclass);


--
-- Name: firma_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firma_convenio ALTER COLUMN id SET DEFAULT nextval('public.firma_convenio_id_seq'::regclass);


--
-- Name: historial_etapa id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_etapa ALTER COLUMN id SET DEFAULT nextval('public.historial_etapa_id_seq'::regclass);


--
-- Name: invitacion_firma_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_firma_convenio ALTER COLUMN id SET DEFAULT nextval('public.invitacion_firma_convenio_id_seq'::regclass);


--
-- Name: invitacion_revision_contraparte id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_revision_contraparte ALTER COLUMN id SET DEFAULT nextval('public.invitacion_revision_contraparte_id_seq'::regclass);


--
-- Name: notificacion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacion ALTER COLUMN id SET DEFAULT nextval('public.notificacion_id_seq'::regclass);


--
-- Name: observacion_revision id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision ALTER COLUMN id SET DEFAULT nextval('public.observacion_revision_id_seq'::regclass);


--
-- Name: pais id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pais ALTER COLUMN id SET DEFAULT nextval('public.pais_id_seq'::regclass);


--
-- Name: plantilla_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plantilla_convenio ALTER COLUMN id SET DEFAULT nextval('public.plantilla_convenio_id_seq'::regclass);


--
-- Name: proceso_firmas_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_firmas_convenio ALTER COLUMN id SET DEFAULT nextval('public.proceso_firmas_convenio_id_seq'::regclass);


--
-- Name: respuesta_revision_contraparte id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_revision_contraparte ALTER COLUMN id SET DEFAULT nextval('public.respuesta_revision_contraparte_id_seq'::regclass);


--
-- Name: revision_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio ALTER COLUMN id SET DEFAULT nextval('public.revision_convenio_id_seq'::regclass);


--
-- Name: rol id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rol ALTER COLUMN id SET DEFAULT nextval('public.rol_id_seq'::regclass);


--
-- Name: solicitud_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio ALTER COLUMN id SET DEFAULT nextval('public.solicitud_convenio_id_seq'::regclass);


--
-- Name: solicitud_usuario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_usuario ALTER COLUMN id SET DEFAULT nextval('public.solicitud_usuario_id_seq'::regclass);


--
-- Name: solicitud_version id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version ALTER COLUMN id SET DEFAULT nextval('public.solicitud_version_id_seq'::regclass);


--
-- Name: tipo_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_convenio ALTER COLUMN id SET DEFAULT nextval('public.tipo_convenio_id_seq'::regclass);


--
-- Name: token_credencial id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_credencial ALTER COLUMN id SET DEFAULT nextval('public.token_credencial_id_seq'::regclass);


--
-- Name: transicion_estado_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transicion_estado_convenio ALTER COLUMN id SET DEFAULT nextval('public.transicion_estado_convenio_id_seq'::regclass);


--
-- Name: unidad_organizacional id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidad_organizacional ALTER COLUMN id SET DEFAULT nextval('public.unidad_organizacional_id_seq'::regclass);


--
-- Name: usuario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario ALTER COLUMN id SET DEFAULT nextval('public.usuario_id_seq'::regclass);


--
-- Name: version_convenio id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_convenio ALTER COLUMN id SET DEFAULT nextval('public.version_convenio_id_seq'::regclass);


--
-- Name: actividad_convenio actividad_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_convenio
    ADD CONSTRAINT actividad_convenio_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: aliado aliado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aliado
    ADD CONSTRAINT aliado_pkey PRIMARY KEY (id);


--
-- Name: auditoria auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_pkey PRIMARY KEY (id);


--
-- Name: borrador_convenio borrador_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.borrador_convenio
    ADD CONSTRAINT borrador_convenio_pkey PRIMARY KEY (id);


--
-- Name: contacto_aliado contacto_aliado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacto_aliado
    ADD CONSTRAINT contacto_aliado_pkey PRIMARY KEY (id);


--
-- Name: contador_codigo_convenio contador_codigo_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contador_codigo_convenio
    ADD CONSTRAINT contador_codigo_convenio_pkey PRIMARY KEY (anio);


--
-- Name: convenio convenio_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_codigo_key UNIQUE (codigo);


--
-- Name: convenio convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_pkey PRIMARY KEY (id);


--
-- Name: convenio convenio_solicitud_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_solicitud_id_key UNIQUE (solicitud_id);


--
-- Name: decision_no_renovacion decision_no_renovacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decision_no_renovacion
    ADD CONSTRAINT decision_no_renovacion_pkey PRIMARY KEY (id);


--
-- Name: documento documento_solicitud_clave_objeto_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_solicitud_clave_objeto_key UNIQUE (ruta_almacenamiento);


--
-- Name: documento documento_solicitud_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_solicitud_pkey PRIMARY KEY (id);


--
-- Name: estado_guia_usuario estado_guia_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_guia_usuario
    ADD CONSTRAINT estado_guia_usuario_pkey PRIMARY KEY (id);


--
-- Name: etapa etapa_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etapa
    ADD CONSTRAINT etapa_codigo_key UNIQUE (codigo);


--
-- Name: etapa etapa_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etapa
    ADD CONSTRAINT etapa_nombre_key UNIQUE (nombre);


--
-- Name: etapa etapa_orden_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etapa
    ADD CONSTRAINT etapa_orden_key UNIQUE (orden);


--
-- Name: etapa etapa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etapa
    ADD CONSTRAINT etapa_pkey PRIMARY KEY (id);


--
-- Name: evaluacion_convenio evaluacion_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluacion_convenio
    ADD CONSTRAINT evaluacion_convenio_pkey PRIMARY KEY (id);


--
-- Name: firma_convenio firma_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firma_convenio
    ADD CONSTRAINT firma_convenio_pkey PRIMARY KEY (id);


--
-- Name: historial_etapa historial_etapa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_etapa
    ADD CONSTRAINT historial_etapa_pkey PRIMARY KEY (id);


--
-- Name: invitacion_firma_convenio invitacion_firma_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_firma_convenio
    ADD CONSTRAINT invitacion_firma_convenio_pkey PRIMARY KEY (id);


--
-- Name: invitacion_revision_contraparte invitacion_revision_contraparte_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_revision_contraparte
    ADD CONSTRAINT invitacion_revision_contraparte_pkey PRIMARY KEY (id);


--
-- Name: notificacion notificacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacion
    ADD CONSTRAINT notificacion_pkey PRIMARY KEY (id);


--
-- Name: observacion_revision observacion_revision_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision
    ADD CONSTRAINT observacion_revision_pkey PRIMARY KEY (id);


--
-- Name: pais pais_codigo_iso_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pais
    ADD CONSTRAINT pais_codigo_iso_key UNIQUE (codigo_iso);


--
-- Name: pais pais_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pais
    ADD CONSTRAINT pais_nombre_key UNIQUE (nombre);


--
-- Name: pais pais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pais
    ADD CONSTRAINT pais_pkey PRIMARY KEY (id);


--
-- Name: plantilla_convenio plantilla_convenio_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plantilla_convenio
    ADD CONSTRAINT plantilla_convenio_codigo_key UNIQUE (codigo);


--
-- Name: plantilla_convenio plantilla_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plantilla_convenio
    ADD CONSTRAINT plantilla_convenio_pkey PRIMARY KEY (id);


--
-- Name: proceso_firmas_convenio proceso_firmas_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_firmas_convenio
    ADD CONSTRAINT proceso_firmas_convenio_pkey PRIMARY KEY (id);


--
-- Name: proceso_firmas_convenio proceso_firmas_convenio_revision_final_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_firmas_convenio
    ADD CONSTRAINT proceso_firmas_convenio_revision_final_id_key UNIQUE (revision_final_id);


--
-- Name: respuesta_revision_contraparte respuesta_revision_contraparte_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_revision_contraparte
    ADD CONSTRAINT respuesta_revision_contraparte_pkey PRIMARY KEY (id);


--
-- Name: respuesta_revision_contraparte respuesta_revision_contraparte_revision_convenio_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_revision_contraparte
    ADD CONSTRAINT respuesta_revision_contraparte_revision_convenio_id_key UNIQUE (revision_convenio_id);


--
-- Name: revision_convenio revision_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT revision_convenio_pkey PRIMARY KEY (id);


--
-- Name: rol rol_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rol
    ADD CONSTRAINT rol_codigo_key UNIQUE (codigo);


--
-- Name: rol rol_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rol
    ADD CONSTRAINT rol_pkey PRIMARY KEY (id);


--
-- Name: solicitud_convenio solicitud_convenio_consecutivo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT solicitud_convenio_consecutivo_key UNIQUE (consecutivo);


--
-- Name: solicitud_convenio solicitud_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT solicitud_convenio_pkey PRIMARY KEY (id);


--
-- Name: solicitud_usuario solicitud_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_usuario
    ADD CONSTRAINT solicitud_usuario_pkey PRIMARY KEY (id);


--
-- Name: solicitud_version_documento solicitud_version_documento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version_documento
    ADD CONSTRAINT solicitud_version_documento_pkey PRIMARY KEY (solicitud_version_id, documento_id);


--
-- Name: solicitud_version solicitud_version_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version
    ADD CONSTRAINT solicitud_version_pkey PRIMARY KEY (id);


--
-- Name: tipo_convenio tipo_convenio_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_convenio
    ADD CONSTRAINT tipo_convenio_codigo_key UNIQUE (codigo);


--
-- Name: tipo_convenio tipo_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipo_convenio
    ADD CONSTRAINT tipo_convenio_pkey PRIMARY KEY (id);


--
-- Name: token_credencial token_credencial_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_credencial
    ADD CONSTRAINT token_credencial_pkey PRIMARY KEY (id);


--
-- Name: transicion_estado_convenio transicion_estado_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transicion_estado_convenio
    ADD CONSTRAINT transicion_estado_convenio_pkey PRIMARY KEY (id);


--
-- Name: unidad_organizacional unidad_organizacional_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidad_organizacional
    ADD CONSTRAINT unidad_organizacional_codigo_key UNIQUE (codigo);


--
-- Name: unidad_organizacional unidad_organizacional_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidad_organizacional
    ADD CONSTRAINT unidad_organizacional_pkey PRIMARY KEY (id);


--
-- Name: aliado uq_aliado_tipo_identificacion; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aliado
    ADD CONSTRAINT uq_aliado_tipo_identificacion UNIQUE (tipo_identificacion, identificacion);


--
-- Name: borrador_convenio uq_borrador_convenio_convenio; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.borrador_convenio
    ADD CONSTRAINT uq_borrador_convenio_convenio UNIQUE (convenio_id);


--
-- Name: contacto_aliado uq_contacto_aliado_correo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacto_aliado
    ADD CONSTRAINT uq_contacto_aliado_correo UNIQUE (aliado_id, correo);


--
-- Name: decision_no_renovacion uq_decision_no_renovacion_convenio_periodo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decision_no_renovacion
    ADD CONSTRAINT uq_decision_no_renovacion_convenio_periodo UNIQUE (convenio_id, fecha_vencimiento_origen);


--
-- Name: estado_guia_usuario uq_estado_guia_usuario_usuario_guia; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_guia_usuario
    ADD CONSTRAINT uq_estado_guia_usuario_usuario_guia UNIQUE (usuario_id, guia);


--
-- Name: evaluacion_convenio uq_evaluacion_convenio_convenio; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluacion_convenio
    ADD CONSTRAINT uq_evaluacion_convenio_convenio UNIQUE (convenio_id);


--
-- Name: firma_convenio uq_firma_convenio_proceso_orden; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firma_convenio
    ADD CONSTRAINT uq_firma_convenio_proceso_orden UNIQUE (proceso_firmas_id, orden);


--
-- Name: firma_convenio uq_firma_convenio_proceso_rol; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firma_convenio
    ADD CONSTRAINT uq_firma_convenio_proceso_rol UNIQUE (proceso_firmas_id, rol_firmante);


--
-- Name: revision_convenio uq_revision_convenio_ronda_instancia; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT uq_revision_convenio_ronda_instancia UNIQUE (convenio_id, tipo, numero_ronda, instancia_juridica);


--
-- Name: solicitud_usuario uq_solicitud_usuario; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_usuario
    ADD CONSTRAINT uq_solicitud_usuario UNIQUE (solicitud_id, usuario_id);


--
-- Name: solicitud_version uq_solicitud_version_numero; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version
    ADD CONSTRAINT uq_solicitud_version_numero UNIQUE (solicitud_id, numero);


--
-- Name: version_convenio uq_version_convenio_numero; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_convenio
    ADD CONSTRAINT uq_version_convenio_numero UNIQUE (convenio_id, numero);


--
-- Name: usuario usuario_correo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_correo_key UNIQUE (correo);


--
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id);


--
-- Name: version_convenio version_convenio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_convenio
    ADD CONSTRAINT version_convenio_pkey PRIMARY KEY (id);


--
-- Name: ix_actividad_convenio_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actividad_convenio_convenio_id ON public.actividad_convenio USING btree (convenio_id);


--
-- Name: ix_auditoria_entidad_fecha_hora; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditoria_entidad_fecha_hora ON public.auditoria USING btree (entidad, fecha_hora);


--
-- Name: ix_auditoria_entidad_registro; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditoria_entidad_registro ON public.auditoria USING btree (entidad, registro_id);


--
-- Name: ix_auditoria_fecha_hora; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditoria_fecha_hora ON public.auditoria USING btree (fecha_hora);


--
-- Name: ix_convenio_fecha_firma; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_convenio_fecha_firma ON public.convenio USING btree (fecha_firma);


--
-- Name: ix_convenio_vigencia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_convenio_vigencia ON public.convenio USING btree (fecha_inicio, fecha_vencimiento);


--
-- Name: ix_documento_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_convenio_id ON public.documento USING btree (convenio_id);


--
-- Name: ix_documento_solicitud_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documento_solicitud_id ON public.documento USING btree (solicitud_id);


--
-- Name: ix_estado_guia_usuario_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_estado_guia_usuario_usuario_id ON public.estado_guia_usuario USING btree (usuario_id);


--
-- Name: ix_firma_convenio_documento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_firma_convenio_documento_id ON public.firma_convenio USING btree (documento_id);


--
-- Name: ix_firma_convenio_proceso_firmas_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_firma_convenio_proceso_firmas_id ON public.firma_convenio USING btree (proceso_firmas_id);


--
-- Name: ix_historial_etapa_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historial_etapa_convenio_id ON public.historial_etapa USING btree (convenio_id);


--
-- Name: ix_historial_etapa_fecha_cambio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historial_etapa_fecha_cambio ON public.historial_etapa USING btree (fecha_cambio);


--
-- Name: ix_invitacion_firma_convenio_firma_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invitacion_firma_convenio_firma_convenio_id ON public.invitacion_firma_convenio USING btree (firma_convenio_id);


--
-- Name: ix_invitacion_firma_convenio_generada_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invitacion_firma_convenio_generada_por_id ON public.invitacion_firma_convenio USING btree (generada_por_id);


--
-- Name: ix_invitacion_revision_contraparte_generada_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invitacion_revision_contraparte_generada_por_id ON public.invitacion_revision_contraparte USING btree (generada_por_id);


--
-- Name: ix_invitacion_revision_contraparte_revision_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invitacion_revision_contraparte_revision_convenio_id ON public.invitacion_revision_contraparte USING btree (revision_convenio_id);


--
-- Name: ix_notificacion_creado_en; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notificacion_creado_en ON public.notificacion USING btree (creado_en);


--
-- Name: ix_notificacion_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notificacion_usuario_id ON public.notificacion USING btree (usuario_id);


--
-- Name: ix_observacion_revision_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observacion_revision_convenio_id ON public.observacion_revision USING btree (convenio_id);


--
-- Name: ix_observacion_revision_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observacion_revision_estado ON public.observacion_revision USING btree (estado);


--
-- Name: ix_observacion_revision_historial_etapa_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observacion_revision_historial_etapa_id ON public.observacion_revision USING btree (historial_etapa_id);


--
-- Name: ix_observacion_revision_revision_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observacion_revision_revision_convenio_id ON public.observacion_revision USING btree (revision_convenio_id);


--
-- Name: ix_plantilla_convenio_activa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plantilla_convenio_activa ON public.plantilla_convenio USING btree (activa);


--
-- Name: ix_proceso_firmas_convenio_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_proceso_firmas_convenio_convenio_id ON public.proceso_firmas_convenio USING btree (convenio_id);


--
-- Name: ix_proceso_firmas_convenio_version_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_proceso_firmas_convenio_version_convenio_id ON public.proceso_firmas_convenio USING btree (version_convenio_id);


--
-- Name: ix_revision_convenio_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_revision_convenio_convenio_id ON public.revision_convenio USING btree (convenio_id);


--
-- Name: ix_revision_convenio_creada_por_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_revision_convenio_creada_por_id ON public.revision_convenio USING btree (creada_por_id);


--
-- Name: ix_revision_convenio_documento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_revision_convenio_documento_id ON public.revision_convenio USING btree (documento_id);


--
-- Name: ix_revision_convenio_version_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_revision_convenio_version_convenio_id ON public.revision_convenio USING btree (version_convenio_id);


--
-- Name: ix_revision_convenio_version_resultado_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_revision_convenio_version_resultado_id ON public.revision_convenio USING btree (version_resultado_id);


--
-- Name: ix_solicitud_convenio_solicitante_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitud_convenio_solicitante_estado ON public.solicitud_convenio USING btree (solicitante_id, estado);


--
-- Name: ix_solicitud_usuario_solicitud_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitud_usuario_solicitud_id ON public.solicitud_usuario USING btree (solicitud_id);


--
-- Name: ix_solicitud_usuario_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitud_usuario_usuario_id ON public.solicitud_usuario USING btree (usuario_id);


--
-- Name: ix_solicitud_version_documento_documento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitud_version_documento_documento_id ON public.solicitud_version_documento USING btree (documento_id);


--
-- Name: ix_token_credencial_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_token_credencial_token_hash ON public.token_credencial USING btree (token_hash);


--
-- Name: ix_token_credencial_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_token_credencial_usuario_id ON public.token_credencial USING btree (usuario_id);


--
-- Name: ix_transicion_estado_convenio_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transicion_estado_convenio_convenio_id ON public.transicion_estado_convenio USING btree (convenio_id);


--
-- Name: ix_version_convenio_convenio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_version_convenio_convenio_id ON public.version_convenio USING btree (convenio_id);


--
-- Name: ix_version_convenio_creado_en; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_version_convenio_creado_en ON public.version_convenio USING btree (creado_en);


--
-- Name: uq_convenio_origen_renovacion_activa; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_convenio_origen_renovacion_activa ON public.convenio USING btree (convenio_origen_id) WHERE ((convenio_origen_id IS NOT NULL) AND ((estado)::text = 'EN_TRAMITE'::text));


--
-- Name: uq_invitacion_contraparte_activa; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_invitacion_contraparte_activa ON public.invitacion_revision_contraparte USING btree (revision_convenio_id) WHERE ((utilizado_en IS NULL) AND (revocado_en IS NULL));


--
-- Name: uq_invitacion_contraparte_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_invitacion_contraparte_token_hash ON public.invitacion_revision_contraparte USING btree (token_hash);


--
-- Name: uq_invitacion_firma_activa; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_invitacion_firma_activa ON public.invitacion_firma_convenio USING btree (firma_convenio_id) WHERE ((utilizado_en IS NULL) AND (revocado_en IS NULL));


--
-- Name: uq_invitacion_firma_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_invitacion_firma_token_hash ON public.invitacion_firma_convenio USING btree (token_hash);


--
-- Name: uq_notificacion_pendiente_por_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_notificacion_pendiente_por_usuario ON public.notificacion USING btree (usuario_id, tipo, entidad_tipo, entidad_id) WHERE (resuelta = false);


--
-- Name: uq_proceso_firmas_convenio_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_proceso_firmas_convenio_activo ON public.proceso_firmas_convenio USING btree (convenio_id) WHERE ((estado)::text = ANY ((ARRAY['CONFIGURACION'::character varying, 'EN_CURSO'::character varying])::text[]));


--
-- Name: uq_revision_convenio_contraparte_pendiente; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_revision_convenio_contraparte_pendiente ON public.revision_convenio USING btree (convenio_id) WHERE (((tipo)::text = 'CONTRAPARTE'::text) AND ((estado)::text = 'PENDIENTE'::text));


--
-- Name: uq_revision_convenio_final_pendiente; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_revision_convenio_final_pendiente ON public.revision_convenio USING btree (convenio_id) WHERE (((tipo)::text = 'FINAL'::text) AND ((estado)::text = 'PENDIENTE'::text));


--
-- Name: uq_revision_convenio_juridica_pendiente; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_revision_convenio_juridica_pendiente ON public.revision_convenio USING btree (convenio_id) WHERE (((tipo)::text = 'JURIDICA'::text) AND ((estado)::text = 'PENDIENTE'::text));


--
-- Name: auditoria tr_auditoria_completar_rol; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tr_auditoria_completar_rol BEFORE INSERT ON public.auditoria FOR EACH ROW EXECUTE FUNCTION public.auditoria_completar_rol();


--
-- Name: auditoria tr_auditoria_no_sobrescribible; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tr_auditoria_no_sobrescribible BEFORE UPDATE ON public.auditoria FOR EACH ROW EXECUTE FUNCTION public.auditoria_no_sobrescribible();


--
-- Name: actividad_convenio actividad_convenio_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_convenio
    ADD CONSTRAINT actividad_convenio_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: actividad_convenio actividad_convenio_registrado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_convenio
    ADD CONSTRAINT actividad_convenio_registrado_por_id_fkey FOREIGN KEY (registrado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: actividad_convenio actividad_convenio_responsable_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_convenio
    ADD CONSTRAINT actividad_convenio_responsable_id_fkey FOREIGN KEY (responsable_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: aliado aliado_pais_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aliado
    ADD CONSTRAINT aliado_pais_id_fkey FOREIGN KEY (pais_id) REFERENCES public.pais(id);


--
-- Name: auditoria auditoria_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: borrador_convenio borrador_convenio_actualizado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.borrador_convenio
    ADD CONSTRAINT borrador_convenio_actualizado_por_id_fkey FOREIGN KEY (actualizado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: borrador_convenio borrador_convenio_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.borrador_convenio
    ADD CONSTRAINT borrador_convenio_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: contacto_aliado contacto_aliado_aliado_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacto_aliado
    ADD CONSTRAINT contacto_aliado_aliado_id_fkey FOREIGN KEY (aliado_id) REFERENCES public.aliado(id) ON DELETE CASCADE;


--
-- Name: convenio convenio_aliado_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_aliado_id_fkey FOREIGN KEY (aliado_id) REFERENCES public.aliado(id);


--
-- Name: convenio convenio_convenio_origen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_convenio_origen_id_fkey FOREIGN KEY (convenio_origen_id) REFERENCES public.convenio(id);


--
-- Name: convenio convenio_creado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_creado_por_id_fkey FOREIGN KEY (creado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: convenio convenio_etapa_actual_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_etapa_actual_id_fkey FOREIGN KEY (etapa_actual_id) REFERENCES public.etapa(id);


--
-- Name: convenio convenio_solicitud_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_solicitud_id_fkey FOREIGN KEY (solicitud_id) REFERENCES public.solicitud_convenio(id);


--
-- Name: convenio convenio_tipo_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_tipo_convenio_id_fkey FOREIGN KEY (tipo_convenio_id) REFERENCES public.tipo_convenio(id);


--
-- Name: convenio convenio_unidad_organizacional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT convenio_unidad_organizacional_id_fkey FOREIGN KEY (unidad_organizacional_id) REFERENCES public.unidad_organizacional(id);


--
-- Name: decision_no_renovacion decision_no_renovacion_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decision_no_renovacion
    ADD CONSTRAINT decision_no_renovacion_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: decision_no_renovacion decision_no_renovacion_decidida_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.decision_no_renovacion
    ADD CONSTRAINT decision_no_renovacion_decidida_por_id_fkey FOREIGN KEY (decidida_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: documento documento_solicitud_solicitud_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_solicitud_solicitud_id_fkey FOREIGN KEY (solicitud_id) REFERENCES public.solicitud_convenio(id) ON DELETE CASCADE;


--
-- Name: estado_guia_usuario estado_guia_usuario_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_guia_usuario
    ADD CONSTRAINT estado_guia_usuario_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: evaluacion_convenio evaluacion_convenio_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluacion_convenio
    ADD CONSTRAINT evaluacion_convenio_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: evaluacion_convenio evaluacion_convenio_evaluado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluacion_convenio
    ADD CONSTRAINT evaluacion_convenio_evaluado_por_id_fkey FOREIGN KEY (evaluado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: firma_convenio firma_convenio_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firma_convenio
    ADD CONSTRAINT firma_convenio_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documento(id) ON DELETE RESTRICT;


--
-- Name: firma_convenio firma_convenio_proceso_firmas_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firma_convenio
    ADD CONSTRAINT firma_convenio_proceso_firmas_id_fkey FOREIGN KEY (proceso_firmas_id) REFERENCES public.proceso_firmas_convenio(id) ON DELETE CASCADE;


--
-- Name: firma_convenio firma_convenio_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.firma_convenio
    ADD CONSTRAINT firma_convenio_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: auditoria fk_auditoria_responsable_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT fk_auditoria_responsable_id_usuario FOREIGN KEY (responsable_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: convenio fk_convenio_plantilla_origen_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.convenio
    ADD CONSTRAINT fk_convenio_plantilla_origen_id FOREIGN KEY (plantilla_origen_id) REFERENCES public.plantilla_convenio(id) ON DELETE RESTRICT;


--
-- Name: documento fk_documento_cargado_por_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT fk_documento_cargado_por_id FOREIGN KEY (cargado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: documento fk_documento_convenio_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT fk_documento_convenio_id FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE CASCADE;


--
-- Name: invitacion_revision_contraparte fk_invitacion_contraparte_generada_por; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_revision_contraparte
    ADD CONSTRAINT fk_invitacion_contraparte_generada_por FOREIGN KEY (generada_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: observacion_revision fk_observacion_revision_revision_convenio_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision
    ADD CONSTRAINT fk_observacion_revision_revision_convenio_id FOREIGN KEY (revision_convenio_id) REFERENCES public.revision_convenio(id) ON DELETE RESTRICT;


--
-- Name: revision_convenio fk_revision_convenio_creada_por_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT fk_revision_convenio_creada_por_id FOREIGN KEY (creada_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: revision_convenio fk_revision_convenio_version_convenio_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT fk_revision_convenio_version_convenio_id FOREIGN KEY (version_convenio_id) REFERENCES public.version_convenio(id) ON DELETE RESTRICT;


--
-- Name: revision_convenio fk_revision_convenio_version_resultado_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT fk_revision_convenio_version_resultado_id FOREIGN KEY (version_resultado_id) REFERENCES public.version_convenio(id) ON DELETE RESTRICT;


--
-- Name: solicitud_convenio fk_solicitud_convenio_decidida_por; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT fk_solicitud_convenio_decidida_por FOREIGN KEY (decidida_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: solicitud_convenio fk_solicitud_convenio_pais_aliado_propuesto_id_pais; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT fk_solicitud_convenio_pais_aliado_propuesto_id_pais FOREIGN KEY (pais_aliado_propuesto_id) REFERENCES public.pais(id);


--
-- Name: solicitud_version fk_solicitud_version_devuelta_por; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version
    ADD CONSTRAINT fk_solicitud_version_devuelta_por FOREIGN KEY (devuelta_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: historial_etapa historial_etapa_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_etapa
    ADD CONSTRAINT historial_etapa_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: historial_etapa historial_etapa_etapa_destino_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_etapa
    ADD CONSTRAINT historial_etapa_etapa_destino_id_fkey FOREIGN KEY (etapa_destino_id) REFERENCES public.etapa(id) ON DELETE RESTRICT;


--
-- Name: historial_etapa historial_etapa_etapa_origen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_etapa
    ADD CONSTRAINT historial_etapa_etapa_origen_id_fkey FOREIGN KEY (etapa_origen_id) REFERENCES public.etapa(id) ON DELETE RESTRICT;


--
-- Name: historial_etapa historial_etapa_responsable_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_etapa
    ADD CONSTRAINT historial_etapa_responsable_id_fkey FOREIGN KEY (responsable_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: historial_etapa historial_etapa_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_etapa
    ADD CONSTRAINT historial_etapa_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: invitacion_firma_convenio invitacion_firma_convenio_firma_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_firma_convenio
    ADD CONSTRAINT invitacion_firma_convenio_firma_convenio_id_fkey FOREIGN KEY (firma_convenio_id) REFERENCES public.firma_convenio(id) ON DELETE CASCADE;


--
-- Name: invitacion_firma_convenio invitacion_firma_convenio_generada_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_firma_convenio
    ADD CONSTRAINT invitacion_firma_convenio_generada_por_id_fkey FOREIGN KEY (generada_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: invitacion_revision_contraparte invitacion_revision_contraparte_revision_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitacion_revision_contraparte
    ADD CONSTRAINT invitacion_revision_contraparte_revision_convenio_id_fkey FOREIGN KEY (revision_convenio_id) REFERENCES public.revision_convenio(id) ON DELETE CASCADE;


--
-- Name: notificacion notificacion_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacion
    ADD CONSTRAINT notificacion_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: observacion_revision observacion_revision_atendida_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision
    ADD CONSTRAINT observacion_revision_atendida_por_id_fkey FOREIGN KEY (atendida_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: observacion_revision observacion_revision_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision
    ADD CONSTRAINT observacion_revision_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE CASCADE;


--
-- Name: observacion_revision observacion_revision_historial_etapa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision
    ADD CONSTRAINT observacion_revision_historial_etapa_id_fkey FOREIGN KEY (historial_etapa_id) REFERENCES public.historial_etapa(id) ON DELETE RESTRICT;


--
-- Name: observacion_revision observacion_revision_registrada_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision
    ADD CONSTRAINT observacion_revision_registrada_por_id_fkey FOREIGN KEY (registrada_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: observacion_revision observacion_revision_responsable_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observacion_revision
    ADD CONSTRAINT observacion_revision_responsable_id_fkey FOREIGN KEY (responsable_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: plantilla_convenio plantilla_convenio_creado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plantilla_convenio
    ADD CONSTRAINT plantilla_convenio_creado_por_id_fkey FOREIGN KEY (creado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: proceso_firmas_convenio proceso_firmas_convenio_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_firmas_convenio
    ADD CONSTRAINT proceso_firmas_convenio_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: proceso_firmas_convenio proceso_firmas_convenio_creado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_firmas_convenio
    ADD CONSTRAINT proceso_firmas_convenio_creado_por_id_fkey FOREIGN KEY (creado_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: proceso_firmas_convenio proceso_firmas_convenio_revision_final_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_firmas_convenio
    ADD CONSTRAINT proceso_firmas_convenio_revision_final_id_fkey FOREIGN KEY (revision_final_id) REFERENCES public.revision_convenio(id) ON DELETE RESTRICT;


--
-- Name: proceso_firmas_convenio proceso_firmas_convenio_version_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proceso_firmas_convenio
    ADD CONSTRAINT proceso_firmas_convenio_version_convenio_id_fkey FOREIGN KEY (version_convenio_id) REFERENCES public.version_convenio(id) ON DELETE RESTRICT;


--
-- Name: respuesta_revision_contraparte respuesta_revision_contraparte_revision_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respuesta_revision_contraparte
    ADD CONSTRAINT respuesta_revision_contraparte_revision_convenio_id_fkey FOREIGN KEY (revision_convenio_id) REFERENCES public.revision_convenio(id) ON DELETE CASCADE;


--
-- Name: revision_convenio revision_convenio_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT revision_convenio_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE CASCADE;


--
-- Name: revision_convenio revision_convenio_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT revision_convenio_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documento(id) ON DELETE RESTRICT;


--
-- Name: revision_convenio revision_convenio_historial_etapa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT revision_convenio_historial_etapa_id_fkey FOREIGN KEY (historial_etapa_id) REFERENCES public.historial_etapa(id) ON DELETE RESTRICT;


--
-- Name: revision_convenio revision_convenio_responsable_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT revision_convenio_responsable_id_fkey FOREIGN KEY (responsable_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: revision_convenio revision_convenio_resuelta_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revision_convenio
    ADD CONSTRAINT revision_convenio_resuelta_por_id_fkey FOREIGN KEY (resuelta_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: solicitud_convenio solicitud_convenio_aliado_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT solicitud_convenio_aliado_id_fkey FOREIGN KEY (aliado_id) REFERENCES public.aliado(id);


--
-- Name: solicitud_convenio solicitud_convenio_solicitante_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT solicitud_convenio_solicitante_id_fkey FOREIGN KEY (solicitante_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: solicitud_convenio solicitud_convenio_tipo_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT solicitud_convenio_tipo_convenio_id_fkey FOREIGN KEY (tipo_convenio_id) REFERENCES public.tipo_convenio(id);


--
-- Name: solicitud_convenio solicitud_convenio_unidad_organizacional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_convenio
    ADD CONSTRAINT solicitud_convenio_unidad_organizacional_id_fkey FOREIGN KEY (unidad_organizacional_id) REFERENCES public.unidad_organizacional(id);


--
-- Name: solicitud_usuario solicitud_usuario_solicitud_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_usuario
    ADD CONSTRAINT solicitud_usuario_solicitud_id_fkey FOREIGN KEY (solicitud_id) REFERENCES public.solicitud_convenio(id) ON DELETE CASCADE;


--
-- Name: solicitud_usuario solicitud_usuario_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_usuario
    ADD CONSTRAINT solicitud_usuario_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE CASCADE;


--
-- Name: solicitud_version_documento solicitud_version_documento_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version_documento
    ADD CONSTRAINT solicitud_version_documento_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documento(id) ON DELETE RESTRICT;


--
-- Name: solicitud_version_documento solicitud_version_documento_solicitud_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version_documento
    ADD CONSTRAINT solicitud_version_documento_solicitud_version_id_fkey FOREIGN KEY (solicitud_version_id) REFERENCES public.solicitud_version(id) ON DELETE CASCADE;


--
-- Name: solicitud_version solicitud_version_radicada_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version
    ADD CONSTRAINT solicitud_version_radicada_por_id_fkey FOREIGN KEY (radicada_por_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: solicitud_version solicitud_version_solicitud_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitud_version
    ADD CONSTRAINT solicitud_version_solicitud_id_fkey FOREIGN KEY (solicitud_id) REFERENCES public.solicitud_convenio(id) ON DELETE RESTRICT;


--
-- Name: token_credencial token_credencial_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_credencial
    ADD CONSTRAINT token_credencial_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuario(id) ON DELETE CASCADE;


--
-- Name: transicion_estado_convenio transicion_estado_convenio_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transicion_estado_convenio
    ADD CONSTRAINT transicion_estado_convenio_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: unidad_organizacional unidad_organizacional_unidad_padre_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidad_organizacional
    ADD CONSTRAINT unidad_organizacional_unidad_padre_id_fkey FOREIGN KEY (unidad_padre_id) REFERENCES public.unidad_organizacional(id);


--
-- Name: usuario usuario_rol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_rol_id_fkey FOREIGN KEY (rol_id) REFERENCES public.rol(id) ON DELETE RESTRICT;


--
-- Name: usuario usuario_unidad_organizacional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_unidad_organizacional_id_fkey FOREIGN KEY (unidad_organizacional_id) REFERENCES public.unidad_organizacional(id);


--
-- Name: version_convenio version_convenio_autor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_convenio
    ADD CONSTRAINT version_convenio_autor_id_fkey FOREIGN KEY (autor_id) REFERENCES public.usuario(id) ON DELETE RESTRICT;


--
-- Name: version_convenio version_convenio_convenio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_convenio
    ADD CONSTRAINT version_convenio_convenio_id_fkey FOREIGN KEY (convenio_id) REFERENCES public.convenio(id) ON DELETE RESTRICT;


--
-- Name: version_convenio version_convenio_etapa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_convenio
    ADD CONSTRAINT version_convenio_etapa_id_fkey FOREIGN KEY (etapa_id) REFERENCES public.etapa(id) ON DELETE RESTRICT;


--
-- Name: version_convenio version_convenio_plantilla_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.version_convenio
    ADD CONSTRAINT version_convenio_plantilla_id_fkey FOREIGN KEY (plantilla_id) REFERENCES public.plantilla_convenio(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict orimanager

