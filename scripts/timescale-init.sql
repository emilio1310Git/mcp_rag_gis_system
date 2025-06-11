-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- Tabla de sensores
CREATE TABLE IF NOT EXISTS sensores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    tipo_sensor VARCHAR(50) NOT NULL,
    estado VARCHAR(20) DEFAULT 'activo',
    fecha_instalacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    localizacion GEOGRAPHY(POINT, 4326) NOT NULL,
    
    -- Metadatos del sensor
    fabricante VARCHAR(100),
    modelo VARCHAR(100),
    numero_serie VARCHAR(100),
    precision_medicion FLOAT,
    rango_min FLOAT,
    rango_max FLOAT,
    unidad_medida VARCHAR(20),
    
    -- Conectividad
    protocolo_comunicacion VARCHAR(50),
    frecuencia_envio INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de refugios de emergencia
CREATE TABLE IF NOT EXISTS refugios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    tipo_refugio VARCHAR(50) NOT NULL,
    
    -- Ubicación
    geom GEOGRAPHY(POINT, 4326) NOT NULL,
    direccion VARCHAR(300),
    municipio VARCHAR(100),
    provincia VARCHAR(100),
    
    -- Capacidad y recursos
    capacidad_maxima INTEGER,
    capacidad_actual INTEGER DEFAULT 0,
    estado_operativo VARCHAR(20) DEFAULT 'disponible',
    
    -- Servicios disponibles
    tiene_agua_potable BOOLEAN DEFAULT TRUE,
    tiene_electricidad BOOLEAN DEFAULT TRUE,
    tiene_calefaccion BOOLEAN DEFAULT FALSE,
    tiene_aire_acondicionado BOOLEAN DEFAULT FALSE,
    tiene_servicio_medico BOOLEAN DEFAULT FALSE,
    tiene_cocina BOOLEAN DEFAULT FALSE,
    
    -- Accesibilidad
    accesible_discapacitados BOOLEAN DEFAULT FALSE,
    acceso_vehicular BOOLEAN DEFAULT TRUE,
    
    -- Información de contacto
    telefono VARCHAR(20),
    email VARCHAR(100),
    responsable VARCHAR(200),
    
    -- Alertas y umbrales
    umbral_temperatura_max FLOAT DEFAULT 40.0,
    umbral_temperatura_min FLOAT DEFAULT -5.0,
    umbral_calidad_aire FLOAT DEFAULT 150.0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de observaciones (Hypertable TimescaleDB)
CREATE TABLE IF NOT EXISTS observaciones (
    id SERIAL,
    sensor_id INTEGER REFERENCES sensores(id),
    
    -- Datos de la medición
    valor FLOAT NOT NULL,
    unidad VARCHAR(20),
    calidad_dato VARCHAR(20) DEFAULT 'buena',
    
    -- Timestamp (columna de particionado TimescaleDB)
    fecha_observacion TIMESTAMP NOT NULL,
    
    -- Localización (puede variar para sensores móviles)
    localizacion GEOGRAPHY(POINT, 4326),
    
    -- Metadatos adicionales
    temperatura_ambiente FLOAT,
    humedad_ambiente FLOAT,
    presion_atmosferica FLOAT,
    velocidad_viento FLOAT,
    direccion_viento FLOAT,
    
    -- Información del dispositivo
    nivel_bateria FLOAT,
    intensidad_senal FLOAT,
    
    -- Procesamiento
    valor_procesado FLOAT,
    algoritmo_procesamiento VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Convertir observaciones en hypertable
SELECT create_hypertable('observaciones', 'fecha_observacion', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Red viaria para rutas (pgRouting)
CREATE TABLE IF NOT EXISTS edges (
    id SERIAL PRIMARY KEY,
    source INTEGER NOT NULL,
    target INTEGER NOT NULL,
    
    -- Costos para routing
    cost FLOAT NOT NULL,
    reverse_cost FLOAT,
    
    -- Información de la vía
    nombre_via VARCHAR(200),
    tipo_via VARCHAR(50),
    estado_via VARCHAR(20) DEFAULT 'transitable',
    
    -- Restricciones
    permitido_vehiculos BOOLEAN DEFAULT TRUE,
    permitido_peatones BOOLEAN DEFAULT TRUE,
    permitido_bicicletas BOOLEAN DEFAULT TRUE,
    
    -- Características físicas
    ancho_metros FLOAT,
    pendiente_porcentaje FLOAT,
    superficie VARCHAR(50),
    
    -- Geometría
    geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    longitud_metros FLOAT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nodes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200),
    tipo_nodo VARCHAR(50),
    geom GEOMETRY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de alertas de temperatura
CREATE TABLE IF NOT EXISTS alertas_temperatura (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_id INTEGER REFERENCES sensores(id),
    refugio_id INTEGER REFERENCES refugios(id),
    
    -- Tipo de alerta
    tipo_alerta VARCHAR(50) NOT NULL,
    severidad VARCHAR(20) NOT NULL,
    
    -- Valores que dispararon la alerta
    valor_actual FLOAT NOT NULL,
    umbral_configurado FLOAT NOT NULL,
    duracion_minutos INTEGER,
    
    -- Estado de la alerta
    estado VARCHAR(20) DEFAULT 'activa',
    fecha_deteccion TIMESTAMP NOT NULL,
    fecha_reconocimiento TIMESTAMP,
    fecha_resolucion TIMESTAMP,
    
    -- Respuesta automática
    sms_enviado BOOLEAN DEFAULT FALSE,
    email_enviado BOOLEAN DEFAULT FALSE,
    refugio_notificado BOOLEAN DEFAULT FALSE,
    
    -- Información adicional
    mensaje_alerta TEXT,
    acciones_recomendadas TEXT,
    personal_notificado VARCHAR(500),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices espaciales
CREATE INDEX IF NOT EXISTS idx_sensores_localizacion ON sensores USING GIST (localizacion);
CREATE INDEX IF NOT EXISTS idx_refugios_geom ON refugios USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_observaciones_localizacion ON observaciones USING GIST (localizacion);
CREATE INDEX IF NOT EXISTS idx_edges_geom ON edges USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_nodes_geom ON nodes USING GIST (geom);

-- Índices para TimescaleDB
CREATE INDEX IF NOT EXISTS idx_observaciones_sensor_tiempo ON observaciones (sensor_id, fecha_observacion DESC);
CREATE INDEX IF NOT EXISTS idx_observaciones_valor ON observaciones (valor);
CREATE INDEX IF NOT EXISTS idx_alertas_fecha ON alertas_temperatura (fecha_deteccion);
CREATE INDEX IF NOT EXISTS idx_alertas_estado ON alertas_temperatura (estado);

-- Continuous Aggregates (Agregados continuos)

-- Agregados horarios de temperatura
CREATE MATERIALIZED VIEW IF NOT EXISTS temp_horaria
WITH (timescaledb.continuous) AS
  SELECT time_bucket('1 hour', fecha_observacion) AS hora,
         sensor_id,
         AVG(valor) AS temp_media,
         MIN(valor) AS temp_min,
         MAX(valor) AS temp_max,
         COUNT(*) AS num_observaciones,
         STDDEV(valor) AS desviacion_estandar
  FROM observaciones
  WHERE unidad = '°C' OR unidad = 'celsius'
  GROUP BY hora, sensor_id
WITH NO DATA;

-- Política de refresh para agregados horarios
SELECT add_continuous_aggregate_policy('temp_horaria',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE
);

-- Agregados diarios de temperatura
CREATE MATERIALIZED VIEW IF NOT EXISTS temp_diaria
WITH (timescaledb.continuous) AS
  SELECT time_bucket('1 day', fecha_observacion) AS dia,
         sensor_id,
         AVG(valor) AS temp_media,
         MIN(valor) AS temp_min,
         MAX(valor) AS temp_max,
         COUNT(*) AS num_observaciones,
         COUNT(*) FILTER (WHERE valor > 35) AS horas_calor_extremo,
         COUNT(*) FILTER (WHERE calidad_dato = 'buena')::FLOAT / COUNT(*)::FLOAT * 100 AS calidad_datos_porcentaje
  FROM observaciones
  WHERE unidad = '°C' OR unidad = 'celsius'
  GROUP BY dia, sensor_id
WITH NO DATA;

-- Política de refresh para agregados diarios
SELECT add_continuous_aggregate_policy('temp_diaria',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '6 hours',
    if_not_exists => TRUE
);

-- Función para calcular rutas óptimas a refugios
CREATE OR REPLACE FUNCTION calcular_ruta_refugio(
    sensor_lat FLOAT,
    sensor_lon FLOAT,
    refugio_id INTEGER
) RETURNS TABLE(
    step_seq INTEGER,
    edge_id INTEGER,
    cost FLOAT,
    geojson TEXT
) AS $$
DECLARE
    node_origen INTEGER;
    node_destino INTEGER;
BEGIN
    -- Encontrar nodo más cercano al sensor
    SELECT id INTO node_origen
    FROM nodes
    ORDER BY geom <-> ST_SetSRID(ST_MakePoint(sensor_lon, sensor_lat), 4326)
    LIMIT 1;
    
    -- Encontrar nodo más cercano al refugio
    SELECT n.id INTO node_destino
    FROM nodes n, refugios r
    WHERE r.id = refugio_id
    ORDER BY n.geom <-> r.geom::geometry
    LIMIT 1;
    
    -- Calcular ruta usando pgRouting
    RETURN QUERY
    SELECT 
        dj.seq::INTEGER,
        dj.edge::INTEGER,
        dj.cost::FLOAT,
        ST_AsGeoJSON(e.geom)::TEXT
    FROM pgr_dijkstra(
        'SELECT id, source, target, cost FROM edges WHERE estado_via = ''transitable''',
        node_origen,
        node_destino,
        directed := false
    ) dj
    JOIN edges e ON e.id = dj.edge
    WHERE dj.edge != -1
    ORDER BY dj.seq;
END;
$$ LANGUAGE plpgsql;

-- Función para detectar anomalías en temperatura
CREATE OR REPLACE FUNCTION detectar_anomalia_temperatura(
    p_sensor_id INTEGER,
    p_valor_actual FLOAT,
    p_umbral_desviaciones FLOAT DEFAULT 3.0
) RETURNS BOOLEAN AS $$
DECLARE
    media_historica FLOAT;
    desviacion_historica FLOAT;
    umbral_superior FLOAT;
    umbral_inferior FLOAT;
BEGIN
    -- Calcular media y desviación de las últimas 24 horas
    SELECT AVG(valor), STDDEV(valor)
    INTO media_historica, desviacion_historica
    FROM observaciones
    WHERE sensor_id = p_sensor_id
    AND fecha_observacion >= NOW() - INTERVAL '24 hours'
    AND calidad_dato = 'buena';
    
    -- Si no hay suficientes datos, no detectar anomalía
    IF media_historica IS NULL OR desviacion_historica IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Calcular umbrales
    umbral_superior := media_historica + (p_umbral_desviaciones * desviacion_historica);
    umbral_inferior := media_historica - (p_umbral_desviaciones * desviacion_historica);
    
    -- Verificar si el valor actual está fuera de los umbrales
    RETURN p_valor_actual > umbral_superior OR p_valor_actual < umbral_inferior;
END;
$$ LANGUAGE plpgsql;

-- Trigger para detectar alertas automáticamente
CREATE OR REPLACE FUNCTION trigger_detectar_alertas()
RETURNS TRIGGER AS $$
DECLARE
    refugio_cercano_id INTEGER;
    es_anomalia BOOLEAN;
    tipo_alerta_detectada VARCHAR(50);
    severidad_calculada VARCHAR(20);
BEGIN
    -- Detectar tipo de alerta basado en umbrales
    IF NEW.valor > 40 THEN
        tipo_alerta_detectada := 'calor_extremo';
        IF NEW.valor > 45 THEN
            severidad_calculada := 'critica';
        ELSIF NEW.valor > 42 THEN
            severidad_calculada := 'alta';
        ELSE
            severidad_calculada := 'media';
        END IF;
    ELSIF NEW.valor < 0 THEN
        tipo_alerta_detectada := 'frio_extremo';
        IF NEW.valor < -10 THEN
            severidad_calculada := 'critica';
        ELSIF NEW.valor < -5 THEN
            severidad_calculada := 'alta';
        ELSE
            severidad_calculada := 'media';
        END IF;
    END IF;
    
    -- Detectar anomalías estadísticas
    es_anomalia := detectar_anomalia_temperatura(NEW.sensor_id, NEW.valor);
    
    IF es_anomalia AND tipo_alerta_detectada IS NULL THEN
        tipo_alerta_detectada := 'cambio_brusco';
        severidad_calculada := 'media';
    END IF;
    
    -- Si hay alerta, crear registro
    IF tipo_alerta_detectada IS NOT NULL THEN
        -- Encontrar refugio más cercano
        SELECT r.id INTO refugio_cercano_id
        FROM refugios r, sensores s
        WHERE s.id = NEW.sensor_id
        AND r.estado_operativo = 'disponible'
        ORDER BY r.geom <-> s.localizacion
        LIMIT 1;
        
        -- Insertar alerta
        INSERT INTO alertas_temperatura (
            sensor_id,
            refugio_id,
            tipo_alerta,
            severidad,
            valor_actual,
            umbral_configurado,
            fecha_deteccion,
            mensaje_alerta
        ) VALUES (
            NEW.sensor_id,
            refugio_cercano_id,
            tipo_alerta_detectada,
            severidad_calculada,
            NEW.valor,
            CASE 
                WHEN tipo_alerta_detectada = 'calor_extremo' THEN 40.0
                WHEN tipo_alerta_detectada = 'frio_extremo' THEN 0.0
                ELSE NULL
            END,
            NEW.fecha_observacion,
            format('Alerta de %s detectada en sensor %s con valor %.2f°C', 
                   tipo_alerta_detectada, NEW.sensor_id, NEW.valor)
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear trigger para observaciones
DROP TRIGGER IF EXISTS trigger_alertas_observaciones ON observaciones;
CREATE TRIGGER trigger_alertas_observaciones
    AFTER INSERT ON observaciones
    FOR EACH ROW
    EXECUTE FUNCTION trigger_detectar_alertas();

-- Función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para actualizar timestamps
CREATE TRIGGER update_sensores_updated_at BEFORE UPDATE ON sensores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_refugios_updated_at BEFORE UPDATE ON refugios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_edges_updated_at BEFORE UPDATE ON edges FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_alertas_updated_at BEFORE UPDATE ON alertas_temperatura FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Datos de ejemplo para sensores
INSERT INTO sensores (nombre, tipo_sensor, localizacion, unidad_medida, rango_min, rango_max) VALUES
('Sensor Madrid Centro', 'temperatura', ST_GeomFromText('POINT(-3.7038 40.4168)', 4326), '°C', -20, 60),
('Sensor Barcelona Eixample', 'temperatura', ST_GeomFromText('POINT(2.1734 41.3851)', 4326), '°C', -10, 50),
('Sensor Zaragoza Centro', 'temperatura', ST_GeomFromText('POINT(-0.8877 41.6488)', 4326), '°C', -15, 55),
('Sensor Valencia Puerto', 'temperatura', ST_GeomFromText('POINT(-0.3762 39.4699)', 4326), '°C', -5, 45)
ON CONFLICT DO NOTHING;

-- Datos de ejemplo para red viaria (simplificado)
INSERT INTO nodes (nombre, tipo_nodo, geom) VALUES
('Nodo Madrid Centro', 'cruce', ST_GeomFromText('POINT(-3.7038 40.4168)', 4326)),
('Nodo Madrid Norte', 'cruce', ST_GeomFromText('POINT(-3.7028 40.4178)', 4326)),
('Nodo Barcelona Centro', 'cruce', ST_GeomFromText('POINT(2.1734 41.3851)', 4326)),
('Nodo Barcelona Este', 'cruce', ST_GeomFromText('POINT(2.1744 41.3861)', 4326)),
('Nodo Zaragoza Centro', 'cruce', ST_GeomFromText('POINT(-0.8877 41.6488)', 4326)),
('Nodo Zaragoza Norte', 'cruce', ST_GeomFromText('POINT(-0.8867 41.6498)', 4326))
ON CONFLICT DO NOTHING;

INSERT INTO edges (source, target, cost, nombre_via, tipo_via, geom, longitud_metros) VALUES
(1, 2, 5.0, 'Calle Mayor Madrid', 'local', ST_GeomFromText('LINESTRING(-3.7038 40.4168, -3.7028 40.4178)', 4326), 1200),
(3, 4, 4.0, 'Passeig de Gràcia', 'local', ST_GeomFromText('LINESTRING(2.1734 41.3851, 2.1744 41.3861)', 4326), 1100),
(5, 6, 3.0, 'Calle Alfonso I', 'local', ST_GeomFromText('LINESTRING(-0.8877 41.6488, -0.8867 41.6498)', 4326), 1000)
ON CONFLICT DO NOTHING;

-- Datos de ejemplo para observaciones (últimas 24 horas)
DO $
DECLARE
    sensor_rec RECORD;
    hora_actual TIMESTAMP;
    i INTEGER;
    temp_base FLOAT;
    temp_variacion FLOAT;
BEGIN
    -- Para cada sensor, generar observaciones cada hora
    FOR sensor_rec IN SELECT id, nombre FROM sensores LOOP
        -- Temperatura base según ubicación
        temp_base := CASE 
            WHEN sensor_rec.nombre LIKE '%Madrid%' THEN 22.0
            WHEN sensor_rec.nombre LIKE '%Barcelona%' THEN 20.0
            WHEN sensor_rec.nombre LIKE '%Zaragoza%' THEN 18.0
            WHEN sensor_rec.nombre LIKE '%Valencia%' THEN 25.0
            ELSE 20.0
        END;
        
        -- Generar observaciones para las últimas 24 horas
        FOR i IN 0..23 LOOP
            hora_actual := NOW() - INTERVAL '23 hours' + (i * INTERVAL '1 hour');
            temp_variacion := (RANDOM() - 0.5) * 10; -- Variación de ±5°C
            
            INSERT INTO observaciones (
                sensor_id,
                valor,
                unidad,
                fecha_observacion,
                calidad_dato,
                nivel_bateria,
                intensidad_senal
            ) VALUES (
                sensor_rec.id,
                temp_base + temp_variacion + 
                    CASE -- Variación diurna
                        WHEN EXTRACT(hour FROM hora_actual) BETWEEN 6 AND 18 THEN 3.0
                        ELSE -2.0
                    END,
                '°C',
                hora_actual,
                CASE WHEN RANDOM() > 0.05 THEN 'buena' ELSE 'regular' END,
                80 + RANDOM() * 20, -- Batería entre 80-100%
                -60 + RANDOM() * 20  -- Señal entre -60 y -40 dBm
            );
        END LOOP;
    END LOOP;
END $;

-- Insertar algunas observaciones extremas para probar alertas
INSERT INTO observaciones (sensor_id, valor, unidad, fecha_observacion, calidad_dato) VALUES
((SELECT id FROM sensores WHERE nombre LIKE '%Madrid%' LIMIT 1), 43.5, '°C', NOW() - INTERVAL '1 hour', 'buena'),
((SELECT id FROM sensores WHERE nombre LIKE '%Barcelona%' LIMIT 1), -2.0, '°C', NOW() - INTERVAL '30 minutes', 'buena');

-- Refresh inicial de los continuous aggregates
CALL refresh_continuous_aggregate('temp_horaria', NULL, NULL);
CALL refresh_continuous_aggregate('temp_diaria', NULL, NULL);

-- Política de retención de datos (conservar 1 año)
SELECT add_retention_policy('observaciones', INTERVAL '1 year', if_not_exists => TRUE);

-- Crear índices adicionales para optimización
CREATE INDEX IF NOT EXISTS idx_observaciones_calidad ON observaciones (calidad_dato);
CREATE INDEX IF NOT EXISTS idx_sensores_tipo ON sensores (tipo_sensor);
CREATE INDEX IF NOT EXISTS idx_refugios_estado ON refugios (estado_operativo);
CREATE INDEX IF NOT EXISTS idx_refugios_capacidad ON refugios (capacidad_actual, capacidad_maxima);

-- Vista para estadísticas en tiempo real
CREATE OR REPLACE VIEW estadisticas_tiempo_real AS
SELECT 
    s.id as sensor_id,
    s.nombre as sensor_nombre,
    s.tipo_sensor,
    ROUND(AVG(o.valor), 2) as temp_promedio_ultima_hora,
    ROUND(MIN(o.valor), 2) as temp_minima_ultima_hora,
    ROUND(MAX(o.valor), 2) as temp_maxima_ultima_hora,
    COUNT(*) as num_observaciones,
    COUNT(*) FILTER (WHERE o.calidad_dato = 'buena') as observaciones_buena_calidad,
    ROUND(AVG(o.nivel_bateria), 1) as bateria_promedio,
    ROUND(AVG(o.intensidad_senal), 1) as senal_promedio,
    MAX(o.fecha_observacion) as ultima_observacion
FROM sensores s
LEFT JOIN observaciones o ON s.id = o.sensor_id 
    AND o.fecha_observacion >= NOW() - INTERVAL '1 hour'
GROUP BY s.id, s.nombre, s.tipo_sensor
ORDER BY s.nombre;

-- Vista para refugios con información de alertas cercanas
CREATE OR REPLACE VIEW refugios_estado_alertas AS
SELECT 
    r.id as refugio_id,
    r.nombre as refugio_nombre,
    r.estado_operativo,
    r.capacidad_actual,
    r.capacidad_maxima,
    ROUND((r.capacidad_actual::FLOAT / r.capacidad_maxima::FLOAT * 100), 1) as porcentaje_ocupacion,
    COUNT(a.id) as alertas_activas_cercanas,
    COUNT(a.id) FILTER (WHERE a.severidad = 'critica') as alertas_criticas,
    COUNT(a.id) FILTER (WHERE a.severidad = 'alta') as alertas_altas,
    MAX(a.fecha_deteccion) as ultima_alerta_cercana
FROM refugios r
LEFT JOIN alertas_temperatura a ON r.id = a.refugio_id 
    AND a.estado = 'activa'
    AND a.fecha_deteccion >= NOW() - INTERVAL '24 hours'
GROUP BY r.id, r.nombre, r.estado_operativo, r.capacidad_actual, r.capacidad_maxima
ORDER BY alertas_criticas DESC, alertas_altas DESC, r.nombre;

-- Función para obtener resumen de alertas por zona
CREATE OR REPLACE FUNCTION resumen_alertas_zona(
    zona_lat FLOAT,
    zona_lon FLOAT,
    radio_km FLOAT DEFAULT 10.0
) RETURNS TABLE(
    total_alertas BIGINT,
    alertas_criticas BIGINT,
    alertas_altas BIGINT,
    alertas_medias BIGINT,
    refugios_disponibles BIGINT,
    capacidad_total_refugios BIGINT
) AS $
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(a.id) as total_alertas,
        COUNT(a.id) FILTER (WHERE a.severidad = 'critica') as alertas_criticas,
        COUNT(a.id) FILTER (WHERE a.severidad = 'alta') as alertas_altas,
        COUNT(a.id) FILTER (WHERE a.severidad = 'media') as alertas_medias,
        COUNT(DISTINCT r.id) FILTER (WHERE r.estado_operativo = 'disponible') as refugios_disponibles,
        COALESCE(SUM(r.capacidad_maxima) FILTER (WHERE r.estado_operativo = 'disponible'), 0) as capacidad_total_refugios
    FROM alertas_temperatura a
    LEFT JOIN sensores s ON a.sensor_id = s.id
    LEFT JOIN refugios r ON ST_DWithin(
        r.geom::geography, 
        ST_Point(zona_lon, zona_lat)::geography, 
        radio_km * 1000
    )
    WHERE a.estado = 'activa'
    AND a.fecha_deteccion >= NOW() - INTERVAL '24 hours'
    AND ST_DWithin(
        s.localizacion::geography,
        ST_Point(zona_lon, zona_lat)::geography,
        radio_km * 1000
    );
END;
$ LANGUAGE plpgsql;fugios
INSERT INTO refugios (nombre, tipo_refugio, geom, municipio, capacidad_maxima, tiene_aire_acondicionado, tiene_calefaccion) VALUES
('Refugio Emergencia Madrid', 'temporal', ST_GeomFromText('POINT(-3.7028 40.4178)', 4326), 'Madrid', 200, TRUE, TRUE),
('Centro Evacuación Barcelona', 'permanente', ST_GeomFromText('POINT(2.1744 41.3861)', 4326), 'Barcelona', 150, TRUE, FALSE),
('Albergue Temporal Zaragoza', 'temporal', ST_GeomFromText('POINT(-0.8867 41.6498)', 4326), 'Zaragoza', 100, FALSE, TRUE),
('Refugio Valencia', 'especializado', ST_GeomFromText('POINT(-0.3752 39.4709)', 4326), 'Valencia', 300, TRUE, FALSE)
ON CONFLICT DO NOTHING;

-- Datos de ejemplo para refugios