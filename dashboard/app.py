#!/usr/bin/env python3
"""
Cold Chain Temperature Monitoring dashboard (Dash + Plotly).

Two data modes:
  * LIVE : subscribes to The Things Stack MQTT server and plots the temperature
           uplinks sent by the LoRaWAN node (4-byte little-endian float payload).
  * DEMO : if no TTN credentials are set, plots simulated readings.

Environment variables:
  TTN_USER, TTN_API_KEY, TTN_REGION (optional), TTN_DEVICE_ID (optional)
  DASH_USERS  optional login list "user1:pass1,user2:pass2" (HTTP Basic Auth)
  TEMP_MIN / TEMP_MAX  alert thresholds in °C (default 0 / 8)
"""
import base64
import json
import os
import random
import struct
import threading
from collections import deque
from datetime import datetime, timedelta

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import dcc, html
from dash.dependencies import Input, Output

TTN_USER = os.getenv("TTN_USER", "")
TTN_API_KEY = os.getenv("TTN_API_KEY", "")
TTN_REGION = os.getenv("TTN_REGION", "eu1.cloud.thethings.network")
TTN_DEVICE_ID = os.getenv("TTN_DEVICE_ID", "")
TEMP_MIN = float(os.getenv("TEMP_MIN", "0"))
TEMP_MAX = float(os.getenv("TEMP_MAX", "8"))

LIVE_MODE = bool(TTN_USER and TTN_API_KEY)
readings = deque(maxlen=500)          # (timestamp, temperature)
lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Data sources
# --------------------------------------------------------------------------- #
def decode_temperature(uplink_message):
    """Return the temperature from a TTN uplink, or None."""
    decoded = uplink_message.get("decoded_payload") or {}
    if "temperature" in decoded:
        return float(decoded["temperature"])
    raw = base64.b64decode(uplink_message.get("frm_payload", ""))
    if len(raw) >= 4:
        return struct.unpack("<f", raw[:4])[0]
    return None


def start_mqtt():
    import paho.mqtt.client as mqtt

    def on_message(client, userdata, message):
        data = json.loads(message.payload)
        up = data.get("uplink_message")
        if not up:
            return
        temp = decode_temperature(up)
        if temp is not None:
            with lock:
                readings.append((datetime.now(), round(temp, 2)))

    client = mqtt.Client()
    client.username_pw_set(TTN_USER, TTN_API_KEY)
    client.tls_set()
    client.on_message = on_message
    client.connect(TTN_REGION, 8883, 60)
    topic = f"v3/{TTN_USER}/devices/{TTN_DEVICE_ID}/up" if TTN_DEVICE_ID else f"v3/{TTN_USER}/devices/+/up"
    client.subscribe(topic, 0)
    client.loop_start()


def demo_readings():
    now = datetime.now()
    return [(now - timedelta(minutes=i), round(random.uniform(-2, 10), 2)) for i in range(60)][::-1]


# --------------------------------------------------------------------------- #
# App & layout
# --------------------------------------------------------------------------- #
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], suppress_callback_exceptions=True)
app.title = "Cold Chain Monitor"

users = os.getenv("DASH_USERS", "")
if users:
    from dash_auth import BasicAuth
    BasicAuth(app, dict(pair.split(":", 1) for pair in users.split(",")))

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Home", href="/")),
        dbc.NavItem(dbc.NavLink("About", href="/about")),
    ],
    brand="Cold Chain Temperature Monitoring",
    brand_href="/",
    color="primary",
    dark=True,
)

home_page = html.Div([
    navbar,
    dbc.Container([
        html.H2("Cold Food Temperature Traceability", className="text-center my-4"),
        html.Div(id="status", className="text-center mb-3"),
        dcc.Graph(id="temperature-graph"),
        dcc.Interval(id="interval-component", interval=5 * 1000, n_intervals=0),
    ]),
])

about_page = html.Div([
    navbar,
    dbc.Container([
        html.H2("About this dashboard", className="my-4"),
        html.P("This dashboard monitors the temperature of cold food storage and transport in real time. "
               "Temperature readings are measured by LoRaWAN sensor nodes, routed through The Things Network "
               "and pushed to the dashboard over MQTT."),
        html.H4("Features"),
        html.Ul([
            html.Li("Real-time temperature monitoring"),
            html.Li(f"Out-of-range alerts (safe range {TEMP_MIN:g} °C to {TEMP_MAX:g} °C)"),
            html.Li("Traceability of the cold chain to support food-safety compliance"),
        ]),
    ]),
])

app.layout = html.Div([dcc.Location(id="url", refresh=False), html.Div(id="page-content")])


@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    if pathname in ("/", None):
        return home_page
    if pathname == "/about":
        return about_page
    return html.H3("404 - Page not found", className="text-center mt-5")


@app.callback(
    [Output("temperature-graph", "figure"), Output("status", "children")],
    [Input("interval-component", "n_intervals")],
)
def update_graph(n):
    if LIVE_MODE:
        with lock:
            data = list(readings)
    else:
        data = demo_readings()

    x = [t for t, _ in data]
    y = [v for _, v in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Temperature"))
    fig.add_hrect(y0=TEMP_MIN, y1=TEMP_MAX, fillcolor="green", opacity=0.1, line_width=0)
    fig.update_layout(
        xaxis_title="Time", yaxis_title="Temperature (°C)",
        margin=dict(l=40, r=40, t=20, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
    )

    mode = "LIVE (TTN MQTT)" if LIVE_MODE else "DEMO (simulated data)"
    if not y:
        return fig, dbc.Alert(f"{mode} - waiting for the first uplink...", color="secondary")
    last = y[-1]
    ok = TEMP_MIN <= last <= TEMP_MAX
    return fig, dbc.Alert(
        f"{mode} - last reading: {last:.2f} °C" + ("" if ok else "  ⚠ OUT OF RANGE"),
        color="success" if ok else "danger",
    )


if __name__ == "__main__":
    if LIVE_MODE:
        start_mqtt()
    app.run(debug=False)
