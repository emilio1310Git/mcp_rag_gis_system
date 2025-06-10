-- Habilitar extensiones PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Crear tabla de secciones censales
CREATE TABLE IF NOT EXISTS secciones_censales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_seccion VARCHAR(20) UNIQUE NOT NULL,
    codigo_distrito VARCHAR(10) NOT NULL,
    codigo_municipio VARCHAR(10) NOT NULL,
    nombre_municipio VARCHAR(100) NOT NULL,
    poblacion INTEGER DEFAULT 0,
    superficie_km2 FLOAT DEFAULT 0.0,
    densidad_hab_km2 FLOAT DEFAULT 0.0,
    geom GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear tabla de equipamientos
CREATE TABLE IF NOT EXISTS equipamientos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(200) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    direccion VARCHAR(300),
    telefono VARCHAR(20),
    website VARCHAR(200),
    horario_apertura VARCHAR(100),
    capacidad INTEGER,
    publico BOOLEAN DEFAULT TRUE,
    geom GEOMETRY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices espaciales
CREATE INDEX IF NOT EXISTS idx_secciones_geom ON secciones_censales USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_equipamientos_geom ON equipamientos USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_equipamientos_tipo ON equipamientos (tipo);
CREATE INDEX IF NOT EXISTS idx_secciones_municipio ON secciones_censales (nombre_municipio);

-- Insertar datos de ejemplo
INSERT INTO secciones_censales (codigo_seccion, codigo_distrito, codigo_municipio, nombre_municipio, poblacion, superficie_km2, densidad_hab_km2, geom) VALUES
('2807901001', '01', '28079', 'Madrid', 1500, 0.5, 3000, ST_GeomFromText('POLYGON((-3.7038 40.4168, -3.7028 40.4168, -3.7028 40.4158, -3.7038 40.4158, -3.7038 40.4168))', 4326)),
('2807901002', '01', '28079', 'Madrid', 2200, 0.8, 2750, ST_GeomFromText('POLYGON((-3.7028 40.4168, -3.7018 40.4168, -3.7018 40.4158, -3.7028 40.4158, -3.7028 40.4168))', 4326)),
('0801402001', '02', '08014', 'Barcelona', 1800, 0.6, 3000, ST_GeomFromText('POLYGON((2.1734 41.3851, 2.1744 41.3851, 2.1744 41.3841, 2.1734 41.3841, 2.1734 41.3851))', 4326))
ON CONFLICT (codigo_seccion) DO NOTHING;

-- Insertar equipamientos de ejemplo
INSERT INTO equipamientos (nombre, tipo, direccion, geom) VALUES
('Hospital Universitario La Paz', 'hospital', 'Paseo de la Castellana, 261, Madrid', ST_GeomFromText('POINT(-3.7033 40.4163)', 4326)),
('CEIP Ramón y Cajal', 'school', 'Calle de Arturo Soria, 52, Madrid', ST_GeomFromText('POINT(-3.7023 40.4163)', 4326)),
('Farmacia Central', 'pharmacy', 'Gran Vía, 123, Madrid', ST_GeomFromText('POINT(-3.7033 40.4153)', 4326)),
('Hospital Clínic', 'hospital', 'Carrer de Villarroel, 170, Barcelona', ST_GeomFromText('POINT(2.1739 41.3846)', 4326))
ON CONFLICT DO NOTHING;

-- Crear función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Crear triggers para actualizar timestamp
CREATE TRIGGER update_secciones_updated_at BEFORE UPDATE ON secciones_censales FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_equipamientos_updated_at BEFORE UPDATE ON equipamientos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();