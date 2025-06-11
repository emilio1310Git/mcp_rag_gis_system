"""Dashboard principal con Dash + Folium para visualización IoT"""

import sys
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dash
from dash import dcc, html, dash_table, Output, Input, State, callback_context
import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
import folium
from folium.plugins import HeatMap
import requests
import json
from datetime import datetime, timedelta
import asyncio
import threading

from config import settings
from services.sensor_service import sensor_service
from database.timescale_client import timescale_client

# Configuración de la aplicación Dash
app = dash.Dash(__name__)
server = app.server

# Layout principal del dashboard
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("🌐 Dashboard IoT - Sistema MCP RAG GIS + TimescaleDB", 
                className="dashboard-title"),
        html.P(f"Monitorización en tiempo real | Actualización cada {settings.dashboard.update_interval/1000}s",
               className="dashboard-subtitle"),
    ], className="header"),
    
    # Controles principales
    html.Div([
        html.Div([
            html.Label("Actualización automática:"),
            dcc.Interval(
                id='interval-component',
                interval=settings.dashboard.update_interval,  # 5 segundos por defecto
                n_intervals=0
            ),
            html.Button("⏸️ Pausar", id="pause-button", n_clicks=0),
            html.Button("🔄 Actualizar", id="refresh-button", n_clicks=0),
        ], className="controls-left"),
        
        html.Div([
            html.Label("Filtros:"),
            dcc.Dropdown(
                id='sensor-type-filter',
                options=[
                    {'label': tipo.title(), 'value': tipo} 
                    for tipo in settings.sensors.supported_types
                ],
                value=settings.sensors.supported_types,
                multi=True,
                placeholder="Seleccionar tipos de sensores"
            ),
        ], className="controls-right"),
    ], className="controls-panel"),
    
    # Métricas principales
    html.Div([
        html.Div([
            html.H3("📱", className="metric-icon"),
            html.H4(id="total-sensors", children="0"),
            html.P("Sensores Totales")
        ], className="metric-card"),
        
        html.Div([
            html.H3("🟢", className="metric-icon"),
            html.H4(id="active-sensors", children="0"),
            html.P("Sensores Activos")
        ], className="metric-card"),
        
        html.Div([
            html.H3("📊", className="metric-icon"),
            html.H4(id="total-readings", children="0"),
            html.P("Lecturas (24h)")
        ], className="metric-card"),
        
        html.Div([
            html.H3("🚨", className="metric-icon"),
            html.H4(id="alerts-count", children="0"),
            html.P("Alertas Activas")
        ], className="metric-card"),
    ], className="metrics-panel"),
    
    # Contenido principal en tabs
    dcc.Tabs(id="main-tabs", value="overview", children=[
        dcc.Tab(label="📊 Resumen", value="overview", children=[
            html.Div([
                # Gráficos en tiempo real
                html.Div([
                    html.H3("📈 Datos en Tiempo Real"),
                    dcc.Graph(id="realtime-chart")
                ], className="chart-container"),
                
                # Mapa de sensores
                html.Div([
                    html.H3("🗺️ Mapa de Sensores"),
                    html.Iframe(id='sensors-map', width='100%', height='500')
                ], className="map-container"),
            ])
        ]),
        
        dcc.Tab(label="📈 Análisis", value="analytics", children=[
            html.Div([
                # Análisis temporal
                html.Div([
                    html.H3("⏰ Análisis Temporal"),
                    html.Div([
                        html.Label("Período de análisis:"),
                        dcc.Dropdown(
                            id='time-period-selector',
                            options=[
                                {'label': '1 Hora', 'value': 1},
                                {'label': '6 Horas', 'value': 6},
                                {'label': '24 Horas', 'value': 24},
                                {'label': '7 Días', 'value': 168}
                            ],
                            value=24
                        ),
                    ], className="selector-container"),
                    dcc.Graph(id="temporal-analysis-chart")
                ], className="analysis-container"),
                
                # Detección de anomalías
                html.Div([
                    html.H3("🚨 Detección de Anomalías"),
                    html.Div([
                        html.Label("Sensor a analizar:"),
                        dcc.Dropdown(id='anomaly-sensor-selector'),
                        html.Label("Tipo de lectura:"),
                        dcc.Dropdown(id='anomaly-type-selector'),
                        html.Button("🔍 Detectar Anomalías", id="detect-anomalies-button"),
                    ], className="anomaly-controls"),
                    html.Div(id="anomaly-results")
                ], className="analysis-container"),
            ])
        ]),
        
        dcc.Tab(label="📋 Datos", value="data", children=[
            html.Div([
                # Tabla de sensores
                html.Div([
                    html.H3("📱 Lista de Sensores"),
                    dash_table.DataTable(
                        id='sensors-table',
                        columns=[
                            {"name": "ID", "id": "sensor_id"},
                            {"name": "Nombre", "id": "name"},
                            {"name": "Tipo", "id": "sensor_type"},
                            {"name": "Activo", "id": "active"},
                            {"name": "Última Lectura", "id": "last_reading"},
                        ],
                        sort_action="native",
                        filter_action="native",
                        page_size=20,
                        style_cell={'textAlign': 'left'},
                        style_data_conditional=[
                            {
                                'if': {'filter_query': '{active} = False'},
                                'backgroundColor': '#ffebee',
                                'color': 'black',
                            }
                        ]
                    )
                ], className="table-container"),
                
                # Datos históricos
                html.Div([
                    html.H3("📊 Datos Históricos"),
                    html.Div([
                        html.Label("Sensor:"),
                        dcc.Dropdown(id='historical-sensor-selector'),
                        html.Label("Tipo de datos:"),
                        dcc.Dropdown(id='historical-type-selector'),
                        html.Button("📥 Exportar CSV", id="export-csv-button"),
                        dcc.Download(id="download-csv"),
                    ], className="historical-controls"),
                    dash_table.DataTable(
                        id='historical-data-table',
                        columns=[
                            {"name": "Timestamp", "id": "timestamp"},
                            {"name": "Valor", "id": "value"},
                            {"name": "Metadata", "id": "metadata"},
                        ],
                        sort_action="native",
                        page_size=50,
                        style_cell={'textAlign': 'left'}
                    )
                ], className="table-container"),
            ])
        ]),
        
        dcc.Tab(label="⚙️ Control", value="control", children=[
            html.Div([
                # Control de simulación
                html.Div([
                    html.H3("🎮 Control de Simulación"),
                    html.Div([
                        html.P(id="simulation-status"),
                        html.Button("▶️ Iniciar", id="start-simulation-button"),
                        html.Button("⏸️ Pausar", id="stop-simulation-button"),
                        html.Button("📊 Estado", id="simulation-status-button"),
                    ], className="simulation-controls"),
                ], className="control-container"),
                
                # Alertas y configuración
                html.Div([
                    html.H3("🚨 Gestión de Alertas"),
                    html.Div([
                        html.Label("Configurar umbrales:"),
                        # Aquí iría un formulario para configurar umbrales
                        html.P("💡 Funcionalidad en desarrollo"),
                    ], className="alerts-config"),
                ], className="control-container"),
                
                # Herramientas de análisis
                html.Div([
                    html.H3("🔧 Herramientas"),
                    html.Div([
                        html.Button("🧹 Limpiar Datos Antiguos", id="cleanup-button"),
                        html.Button("📊 Regenerar Agregados", id="refresh-aggregates-button"),
                        html.Button("🔄 Reiniciar Servicios", id="restart-services-button"),
                    ], className="tools-buttons"),
                    html.Div(id="tools-output")
                ], className="control-container"),
            ])
        ])
    ]),
    
    # Footer
    html.Div([
        html.P(f"Sistema MCP RAG GIS + TimescaleDB v{settings.api.version} | "
               f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")
    ], className="footer", id="footer-timestamp")
    
], className="dashboard-container")

# Callbacks para funcionalidad del dashboard

@app.callback(
    [Output('total-sensors', 'children'),
     Output('active-sensors', 'children'),
     Output('total-readings', 'children'),
     Output('alerts-count', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_metrics(n):
    """Actualizar métricas principales del dashboard"""
    try:
        # Obtener datos de dashboard en tiempo real
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        dashboard_data = loop.run_until_complete(sensor_service.get_real_time_dashboard_data())
        loop.close()
        
        total_sensors = dashboard_data.get('total_sensors', 0)
        active_sensors = dashboard_data.get('active_sensors', 0)
        
        # Calcular lecturas totales de las estadísticas
        stats = dashboard_data.get('statistics', {})
        total_readings = sum(s.get('total_readings', 0) for s in stats.values())
        
        # Alertas (simulado por ahora)
        alerts_count = 0  # Implementar lógica de alertas
        
        return total_sensors, active_sensors, f"{total_readings:,}", alerts_count
        
    except Exception as e:
        return "Error", "Error", "Error", "Error"

@app.callback(
    Output('realtime-chart', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('sensor-type-filter', 'value')]
)
def update_realtime_chart(n, selected_types):
    """Actualizar gráfico de datos en tiempo real"""
    try:
        # Obtener datos en tiempo real
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        real_time_data = loop.run_until_complete(
            timescale_client.get_real_time_data(
                sensor_types=selected_types,
                last_minutes=30
            )
        )
        loop.close()
        
        sensors_data = real_time_data.get('sensors', {})
        
        # Crear trazas para cada tipo de sensor
        traces = []
        colors = px.colors.qualitative.Set1
        
        for i, sensor_type in enumerate(selected_types or []):
            type_values = []
            type_sensors = []
            
            for sensor_id, readings in sensors_data.items():
                if sensor_type in readings:
                    type_values.append(readings[sensor_type]['value'])
                    type_sensors.append(sensor_id)
            
            if type_values:
                traces.append(go.Bar(
                    x=type_sensors,
                    y=type_values,
                    name=sensor_type.title(),
                    marker_color=colors[i % len(colors)]
                ))
        
        layout = go.Layout(
            title="Valores Actuales por Sensor",
            xaxis={'title': 'Sensores'},
            yaxis={'title': 'Valor'},
            height=400,
            showlegend=True
        )
        
        return {'data': traces, 'layout': layout}
        
    except Exception as e:
        return {
            'data': [],
            'layout': go.Layout(
                title="Error cargando datos en tiempo real",
                height=400
            )
        }

@app.callback(
    Output('sensors-map', 'srcDoc'),
    [Input('interval-component', 'n_intervals'),
     Input('sensor-type-filter', 'value')]
)
def update_sensors_map(n, selected_types):
    """Actualizar mapa de sensores"""
    try:
        # Obtener lista de sensores
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sensors = loop.run_until_complete(sensor_service.get_sensors_list())
        real_time_data = loop.run_until_complete(
            timescale_client.get_real_time_data(last_minutes=10)
        )
        loop.close()
        
        # Filtrar sensores por tipo seleccionado
        if selected_types:
            sensors = [s for s in sensors if s['sensor_type'] in selected_types]
        
        if not sensors:
            # Mapa vacío si no hay sensores
            m = folium.Map(location=[40.4168, -3.7038], zoom_start=6)
            folium.Marker(
                [40.4168, -3.7038],
                popup="No hay sensores para mostrar",
                icon=folium.Icon(color='gray')
            ).add_to(m)
            return m.get_root().render()
        
        # Calcular centro del mapa
        center_lat = sum(s['location']['lat'] for s in sensors) / len(sensors)
        center_lon = sum(s['location']['lon'] for s in sensors) / len(sensors)
        
        # Crear mapa
        m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
        
        # Colores por tipo de sensor
        sensor_colors = {
            'temperature': 'red',
            'humidity': 'blue',
            'air_quality': 'green',
            'noise': 'orange',
            'occupancy': 'purple'
        }
        
        # Añadir marcadores de sensores
        for sensor in sensors:
            sensor_id = sensor['sensor_id']
            sensor_type = sensor['sensor_type']
            location = sensor['location']
            
            # Obtener último valor si está disponible
            sensor_data = real_time_data.get('sensors', {}).get(sensor_id, {})
            last_value = "N/A"
            if sensor_type in sensor_data:
                last_value = sensor_data[sensor_type]['value']
            
            # Color del marcador
            color = sensor_colors.get(sensor_type, 'gray')
            
            # Popup con información
            popup_html = f"""
            <div style="width:200px">
                <h4>{sensor['name']}</h4>
                <p><b>ID:</b> {sensor_id}</p>
                <p><b>Tipo:</b> {sensor_type}</p>
                <p><b>Último valor:</b> {last_value}</p>
                <p><b>Estado:</b> {'Activo' if sensor['active'] else 'Inactivo'}</p>
            </div>
            """
            
            folium.Marker(
                [location['lat'], location['lon']],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{sensor['name']} ({sensor_type})",
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)
        
        # Añadir leyenda
        legend_html = f'''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 150px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <h4>Tipos de Sensores</h4>
        '''
        
        for sensor_type in selected_types or []:
            color = sensor_colors.get(sensor_type, 'gray')
            legend_html += f'<p><i class="fa fa-circle" style="color:{color}"></i> {sensor_type.title()}</p>'
        
        legend_html += '</div>'
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m.get_root().render()
        
    except Exception as e:
        # Mapa de error
        m = folium.Map(location=[40.4168, -3.7038], zoom_start=6)
        folium.Marker(
            [40.4168, -3.7038],
            popup=f"Error cargando mapa: {str(e)}",
            icon=folium.Icon(color='red')
        ).add_to(m)
        return m.get_root().render()

@app.callback(
    Output('sensors-table', 'data'),
    [Input('interval-component', 'n_intervals')]
)
def update_sensors_table(n):
    """Actualizar tabla de sensores"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sensors = loop.run_until_complete(sensor_service.get_sensors_list())
        loop.close()
        
        # Formatear datos para la tabla
        table_data = []
        for sensor in sensors:
            table_data.append({
                'sensor_id': sensor['sensor_id'],
                'name': sensor['name'],
                'sensor_type': sensor['sensor_type'],
                'active': '✅' if sensor['active'] else '❌',
                'last_reading': 'En tiempo real'  # Simplificado
            })
        
        return table_data
        
    except Exception as e:
        return [{'sensor_id': 'Error', 'name': str(e), 'sensor_type': '', 'active': '', 'last_reading': ''}]

@app.callback(
    Output('simulation-status', 'children'),
    [Input('simulation-status-button', 'n_clicks'),
     Input('start-simulation-button', 'n_clicks'),
     Input('stop-simulation-button', 'n_clicks')]
)
def control_simulation(status_clicks, start_clicks, stop_clicks):
    """Controlar simulación de sensores"""
    try:
        # Determinar qué botón se presionó
        ctx = callback_context
        if not ctx.triggered:
            button_id = 'simulation-status-button'
        else:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if button_id == 'start-simulation-button':
            loop.run_until_complete(sensor_service.start_simulation())
            result = "🟢 Simulación iniciada correctamente"
        elif button_id == 'stop-simulation-button':
            loop.run_until_complete(sensor_service.stop_simulation())
            result = "🔴 Simulación detenida"
        else:  # status
            is_running = sensor_service.simulation_running
            sensor_count = len(sensor_service.sensors)
            result = f"{'🟢 Activa' if is_running else '🔴 Inactiva'} | {sensor_count} sensores registrados"
        
        loop.close()
        return result
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

# CSS personalizado
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .dashboard-container {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                text-align: center;
            }
            .dashboard-title {
                margin: 0;
                font-size: 2.5em;
                font-weight: 300;
            }
            .dashboard-subtitle {
                margin: 10px 0 0 0;
                opacity: 0.9;
            }
            .controls-panel {
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: white;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .metrics-panel {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .metric-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: transform 0.2s;
            }
            .metric-card:hover {
                transform: translateY(-2px);
            }
            .metric-icon {
                font-size: 2em;
                margin-bottom: 10px;
            }
            .chart-container, .map-container, .analysis-container, .table-container, .control-container {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .footer {
                text-align: center;
                color: #666;
                font-size: 0.9em;
                margin-top: 20px;
            }
            .selector-container, .anomaly-controls, .historical-controls, .simulation-controls, .tools-buttons {
                display: flex;
                gap: 15px;
                align-items: center;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            button {
                background: #667eea;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                transition: background 0.2s;
            }
            button:hover {
                background: #5a6fd8;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Función para ejecutar el dashboard
def run_dashboard():
    """Ejecutar el dashboard"""
    app.run_server(
        host=settings.dashboard.host,
        port=settings.dashboard.port,
        debug=settings.dashboard.debug
    )

if __name__ == "__main__":
    run_dashboard()