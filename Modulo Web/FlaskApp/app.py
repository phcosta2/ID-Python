from __future__ import annotations
import os
from pathlib import Path
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# .env
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

import requests

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-please-change-me")

# ====== USERS em memória (didático) ======
USERS: Dict[str, Dict[str, str]] = {
    "admin@example.com": {"name": "Admin", "password_hash": generate_password_hash("123456")}
}

def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.get("/")
def index():
    return redirect(url_for("home") if "user_email" in session else url_for("login"))

# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = USERS.get(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Credenciais inválidas.", "error")
            return render_template("login.html", email=email), 401
        session["user_email"] = email
        session["user_name"] = user["name"]
        flash(f"Bem-vindo(a), {user['name']}!", "success")
        return redirect(request.args.get("next") or url_for("home"))
    if "user_email" in session:
        return redirect(url_for("home"))
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    flash("Você saiu da sessão.", "info")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            flash("Preencha todos os campos.", "error")
            return render_template("register.html", name=name, email=email), 400
        if email in USERS:
            flash("E-mail já registrado.", "error")
            return render_template("register.html", name=name, email=email), 409
        USERS[email] = {"name": name, "password_hash": generate_password_hash(password)}
        flash("Cadastro realizado! Faça login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

# ---------- Clima (Open-Meteo, sem key) ----------
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "São Bernardo do Campo, BR")
FALLBACK_LATLON = (-23.689, -46.564)  # SBC ~ centro

WEATHER_CODE_PT = {
    0: "Céu limpo", 1: "Principalmente limpo", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Nevoeiro", 48: "Nevoeiro com gelo", 51: "Garoa fraca", 53: "Garoa moderada",
    55: "Garoa intensa", 56: "Garoa congelante fraca", 57: "Garoa congelante intensa",
    61: "Chuva fraca", 63: "Chuva moderada", 65: "Chuva forte",
    66: "Chuva congelante fraca", 67: "Chuva congelante forte",
    71: "Neve fraca", 73: "Neve moderada", 75: "Neve forte",
    77: "Grãos de neve", 80: "Aguaceiros fracos", 81: "Aguaceiros moderados", 82: "Aguaceiros fortes",
    85: "Aguaceiros de neve fracos", 86: "Aguaceiros de neve fortes",
    95: "Trovoadas", 96: "Trovoadas com granizo leve", 97: "Trovoadas com granizo forte",
}

def geocode_city(city: str) -> Optional[Tuple[float, float, str]]:
    # 1) tenta geocodificar
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "pt", "format": "json"},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("results"):
            res = data["results"][0]
            return float(res["latitude"]), float(res["longitude"]), res.get("name", city)
    except Exception:
        pass
    # 2) fallback fixo (SBC)
    lat, lon = FALLBACK_LATLON
    return lat, lon, city


def fetch_current_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Tenta 3 formatos da Open-Meteo:
    1) novo: current=temperature_2m,wind_speed_10m,wind_direction_10m,weather_code
    2) antigo: current_weather=true
    3) derivado: hourly (pega a última hora)
    """
    try:
        # 1) Formato novo
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,wind_speed_10m,wind_direction_10m,weather_code",
                "timezone": "America/Sao_Paulo",
                "wind_speed_unit": "kmh",
            },
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        cur = data.get("current")
        if cur:
            code = int(cur.get("weather_code", -1))
            return {
                "temperature": cur.get("temperature_2m"),
                "windspeed": cur.get("wind_speed_10m"),
                "winddirection": cur.get("wind_direction_10m"),
                "weathercode": code,
                "description": WEATHER_CODE_PT.get(code, f"Código {code}"),
                "time": cur.get("time"),
                "src": "current(new)",
            }

        # 2) Formato antigo
        r2 = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "timezone": "America/Sao_Paulo",
                "windspeed_unit": "kmh",
            },
            timeout=8,
        )
        r2.raise_for_status()
        data2 = r2.json()
        old = data2.get("current_weather")
        if old:
            code = int(old.get("weathercode", -1))
            return {
                "temperature": old.get("temperature"),
                "windspeed": old.get("windspeed"),
                "winddirection": old.get("winddirection"),
                "weathercode": code,
                "description": WEATHER_CODE_PT.get(code, f"Código {code}"),
                "time": old.get("time"),
                "src": "current_weather(old)",
            }

        # 3) Derivação por hourly (pega último valor disponível)
        r3 = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m",
                "timezone": "America/Sao_Paulo",
                "wind_speed_unit": "kmh",
            },
            timeout=8,
        )
        r3.raise_for_status()
        data3 = r3.json()
        h = data3.get("hourly", {})
        times = h.get("time", [])
        if times:
            i = len(times) - 1
            def _get(arr, idx):
                try: return arr[idx]
                except: return None
            code = int(_get(h.get("weather_code", []), i) or -1)
            return {
                "temperature": _get(h.get("temperature_2m", []), i),
                "windspeed": _get(h.get("wind_speed_10m", []), i),
                "winddirection": _get(h.get("wind_direction_10m", []), i),
                "weathercode": code,
                "description": WEATHER_CODE_PT.get(code, f"Código {code}"),
                "time": _get(times, i),
                "src": "hourly(derived)",
            }

        return None
    except Exception:
        return None


@app.get("/home")
@login_required
def home():
    name = session.get("user_name", "Usuário")
    city = DEFAULT_CITY
    weather = None
    resolved_city = None

    geo = geocode_city(city)
    if not geo:
        flash("Não foi possível localizar a cidade padrão.", "error")
    else:
        lat, lon, resolved_city = geo
        weather = fetch_current_weather(lat, lon)
        if not weather:
            flash("Não foi possível obter o clima agora.", "error")

    return render_template("home.html",
                           name=name,
                           city_query=city,
                           city_resolved=resolved_city,
                           weather=weather)

if __name__ == "__main__":
    app.run(debug=bool(int(os.getenv("FLASK_DEBUG", "1"))))
