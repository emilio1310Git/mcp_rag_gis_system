-- Inicialización de TimescaleDB con PostGIS para sistema IoT
-- Este script se ejecuta automáticamente al crear el contenedor

-- Habilitar extensiones
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Configuraciones de rendimiento para TimescaleDB
ALTER SYSTEM SET shared_preload_libraries = 'timescaledb';
ALTER SYSTEM SET max_connections = '200';
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET effective_cache_size = '2GB';

-- Crear esquema para datos IoT
CREATE SCHEMA IF NOT EXISTS iot;

-- Tabla de sensores (ya definida en sensor_service.py pero la creamos aquí también)
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    sensor_type VARCHAR(50) NOT NULL,
    equipment_id UUID,
    location GEOMETRY(POINT, 4326) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de lecturas de sensores (hypertable)
CREATE TABLE IF NOT EXISTS sensor_readings (
    id SERIAL,
    sensor_id VARCHAR(50) NOT NULL,
    reading_type VARCHAR(50) NOT NULL,
    value NUMERIC NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB DEFAULT '{}',
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);

-- Convertir a hypertable (series temporal)
SELECT create_hypertable('sensor_readings', 'timestamp', chunk_time_interval => INTERVAL '7 days');

-- Tabla de alertas
CREATE TABLE IF NOT EXISTS sensor_alerts (
    id SERIAL PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL,
    reading_type VARCHAR(50) NOT NULL,
    value NUMERIC NOT NULL,
    level VARCHAR(20) NOT NULL, -- CRITICAL, WARNING, INFO
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);

-- Índices para optimización
CREATE INDEX IF NOT EXISTS idx_sensors_location ON sensors USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_sensors_type ON sensors (sensor_type);
CREATE INDEX IF NOT EXISTS idx_sensors_active ON sensors (active);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_time ON sensor_readings (sensor_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_type_time ON sensor_readings (reading_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_sensor_alerts_sensor ON sensor_alerts (sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_alerts_timestamp ON sensor_alerts (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_alerts_level ON sensor_alerts (level);
CREATE INDEX IF NOT EXISTS idx_sensor_alerts_resolved ON sensor_alerts (resolved);

-- Continuous aggregates para datos agregados
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', timestamp) AS hour,
       sensor_id,
       reading_type,
       AVG(value) AS avg_value,
       MIN(value) AS min_value,
       MAX(value) AS max_value,
       COUNT(*) AS readings_count,
       STDDEV(value) AS std_value
FROM sensor_readings
GROUP BY hour, sensor_id, reading_type
WITH NO DATA;

-- Agregados diarios
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', timestamp) AS day,
       sensor_id,
       reading_type,
       AVG(value) AS avg_value,
       MIN(value) AS min_value,
       MAX(value) AS max_value,
       COUNT(*) AS readings_count,
       STDDEV(value) AS std_value
FROM sensor_readings
GROUP BY day, sensor_id, reading_type
WITH NO DATA;

-- Políticas de refresh para continuous aggregates
SELECT add_continuous_aggregate_policy('sensor_readings_hourly',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes');

SELECT add_continuous_aggregate_policy('sensor_readings_daily',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour');

-- Política de retención (mantener datos detallados por 30 días)
SELECT add_retention_policy('sensor_readings', INTERVAL '30 days');

-- Función para detectar anomalías en tiempo real
CREATE OR REPLACE FUNCTION detect_reading_anomaly()
RETURNS TRIGGER AS $$
DECLARE
    avg_value NUMERIC;
    std_value NUMERIC;
    z_score NUMERIC;
    threshold NUMERIC := 3.0; -- 3 desviaciones estándar
BEGIN
    -- Calcular promedio y desviación estándar de las últimas 24 horas
    SELECT AVG(value), STDDEV(value)
    INTO avg_value, std_value
    FROM sensor_readings
    WHERE sensor_id = NEW.sensor_id
    AND reading_type = NEW.reading_type
    AND timestamp >= NOW() - INTERVAL '24 hours';
    
    -- Calcular Z-score si hay suficientes datos
    IF std_value > 0 AND avg_value IS NOT NULL THEN
        z_score := ABS(NEW.value - avg_value) / std_value;
        
        -- Si supera el umbral, crear alerta
        IF z_score > threshold THEN
            INSERT INTO sensor_alerts (sensor_id, reading_type, value, level, message, timestamp)
            VALUES (
                NEW.sensor_id,
                NEW.reading_type,
                NEW.value,
                CASE 
                    WHEN z_score > 4.0 THEN 'CRITICAL'
                    ELSE 'WARNING'
                END,
                FORMAT('Anomalía detectada: valor %s (Z-score: %s)', NEW.value, ROUND(z_score, 2)),
                NEW.timestamp
            );
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para detección automática de anomalías
CREATE TRIGGER sensor_reading_anomaly_trigger
    AFTER INSERT ON sensor_readings
    FOR EACH ROW
    EXECUTE FUNCTION detect_reading_anomaly();

-- Función para limpiar alertas resueltas antiguas
CREATE OR REPLACE FUNCTION cleanup_old_alerts()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM sensor_alerts
    WHERE resolved = TRUE 
    AND resolved_at < NOW() - INTERVAL '7 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Vista para estadísticas rápidas de sensores
CREATE OR REPLACE VIEW sensor_stats AS
SELECT 
    s.sensor_id,
    s.name,
    s.sensor_type,
    s.active,
    COUNT(sr.id) as total_readings_24h,
    AVG(sr.value) as avg_value_24h,
    MIN(sr.value) as min_value_24h,
    MAX(sr.value) as max_value_24h,
    MAX(sr.timestamp) as last_reading
FROM sensors s
LEFT JOIN sensor_readings sr ON s.sensor_id = sr.sensor_id
    AND sr.timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY s.sensor_id, s.name, s.sensor_type, s.active;

-- Función para obtener resumen de dashboard
CREATE OR REPLACE FUNCTION get_dashboard_summary()
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'total_sensors', (SELECT COUNT(*) FROM sensors),
        'active_sensors', (SELECT COUNT(*) FROM sensors WHERE active = TRUE),
        'total_readings_24h', (SELECT COUNT(*) FROM sensor_readings WHERE timestamp >= NOW() - INTERVAL '24 hours'),
        'active_alerts', (SELECT COUNT(*) FROM sensor_alerts WHERE resolved = FALSE),
        'sensor_types', (
            SELECT json_agg(json_build_object('type', sensor_type, 'count', cnt))
            FROM (
                SELECT sensor_type, COUNT(*) as cnt
                FROM sensors
                WHERE active = TRUE
                GROUP BY sensor_type
            ) t
        )
    ) INTO result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Insertar datos de ejemplo para demostración
INSERT INTO sensors (sensor_id, name, sensor_type, location, metadata) VALUES
('DEMO_TEMP_001', 'Sensor Temperatura Centro', 'temperature', ST_Point(-3.7038, 40.4168, 4326), '{"demo": true, "location": "Madrid Centro"}'),
('DEMO_HUM_001', 'Sensor Humedad Centro', 'humidity', ST_Point(-3.7028, 40.4168, 4326), '{"demo": true, "location": "Madrid Centro"}'),
('DEMO_AIR_001', 'Sensor Calidad Aire', 'air_quality', ST_Point(-3.7033, 40.4163, 4326), '{"demo": true, "location": "Madrid Centro"}'),
('DEMO_NOISE_001', 'Sensor Ruido Urbano', 'noise', ST_Point(-3.7023, 40.4163, 4326), '{"demo": true, "location": "Madrid Centro"}'),
('DEMO_OCC_001', 'Sensor Ocupación Plaza', 'occupancy', ST_Point(-3.7043, 40.4173, 4326), '{"demo": true, "location": "Plaza Mayor"}')