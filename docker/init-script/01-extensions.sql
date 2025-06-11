-- docker/init-scripts/01-extensions.sql
-- Instalar extensiones necesarias para el sistema ampliado

-- Habilitar TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Habilitar PostGIS para funcionalidades geoespaciales
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Habilitar pgRouting para cálculo de rutas
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- Habilitar extensiones adicionales útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Configurar parámetros de TimescaleDB
SELECT set_config('timescaledb.max_background_workers', '4', false);
SELECT set_config('timescaledb.restoring', 'off', false);

-- Mensaje de confirmación
DO $$
BEGIN
    RAISE NOTICE 'Extensiones TimescaleDB, PostGIS y pgRouting instaladas correctamente';
END
$$;