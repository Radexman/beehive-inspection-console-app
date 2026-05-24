import json
from datetime import date
from pathlib import Path

import questionary
import requests
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from weather_codes import WEATHER_CODES

# ── ścieżki ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
PROFILE_PATH = BASE_DIR / "profile.json"
INSPECTIONS_DIR = BASE_DIR / "inspections"

# ── pogoda (Open-Meteo — darmowe, bez klucza API) ───────────────────────────────
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


# ── profil użytkownika (profile.json) ─────────────────────────────────────────
def load_profile() -> dict | None:
    """Wczytaj profil pszczelarza z profile.json (None, jeśli plik nie istnieje)."""
    if not PROFILE_PATH.exists():
        return None
    with PROFILE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile: dict) -> None:
    """Zapisz profil do profile.json (UTF-8, czytelne wcięcia)."""
    with PROFILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def _is_float(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


# ── 2 · aktualizacja danych użytkownika ───────────────────────────────────────
def update_user_data() -> None:
    """Zbierz dane pszczelarza przez questionary i zapisz je do profile.json."""
    current = load_profile() or {}
    loc = current.get("location", {})

    beekeeper_name = questionary.text(
        "Imię i nazwisko:", default=current.get("beekeeper_name", "")
    ).ask()
    apiary_name = questionary.text(
        "Nazwa pasieki:", default=current.get("apiary_name", "")
    ).ask()
    veterinary_number = questionary.text(
        "Numer weterynaryjny:", default=current.get("veterinary_number", "")
    ).ask()
    lat = questionary.text(
        "Szerokość geo. (lat):",
        default=str(loc.get("lat", "")),
        validate=lambda t: _is_float(t) or "Podaj liczbę, np. 50.7263",
    ).ask()
    lon = questionary.text(
        "Długość geo. (lon):",
        default=str(loc.get("lon", "")),
        validate=lambda t: _is_float(t) or "Podaj liczbę, np. 18.1506",
    ).ask()
    label = questionary.text("Lokalizacja (opis):", default=loc.get("label", "")).ask()

    profile = {
        "beekeeper_name": beekeeper_name,
        "apiary_name": apiary_name,
        "veterinary_number": veterinary_number,
        "location": {
            "lat": float(lat),
            "lon": float(lon),
            "label": label,
        },
    }
    save_profile(profile)
    print(f"\n✓ Zapisano profil: {PROFILE_PATH}")


# ── pobieranie pogody ─────────────────────────────────────────────────────────
def get_weather(lat: float, lon: float) -> dict | None:
    """Pobierz aktualną pogodę z Open-Meteo (darmowe, bez klucza API).

    Zwraca None, gdy zapytanie się nie powiodło — przegląd i tak zostanie
    wygenerowany (pola pogody pozostaną puste).
    """
    try:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": ",".join(
                    [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "weather_code",
                        "wind_speed_10m",
                        "precipitation",
                        "cloud_cover",
                    ]
                ),
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        current = response.json()["current"]
    except requests.RequestException:
        print("⚠ Nie udało się połączyć z Open-Meteo — pomijam pogodę.")
        return None
    except (KeyError, ValueError):
        print("⚠ Nieoczekiwana odpowiedź z Open-Meteo — pomijam pogodę.")
        return None

    return {
        "temp": round(current["temperature_2m"]),
        "humidity": current["relative_humidity_2m"],
        "wind": round(current["wind_speed_10m"]),
        "precipitation": current["precipitation"],
        "cloud_cover": current["cloud_cover"],
        "description": WEATHER_CODES.get(current["weather_code"], "—"),
    }


# ── 1 · nowy przegląd (PDF) ────────────────────────────────────────────────────
def new_inspection() -> None:
    """Wygeneruj PDF przeglądu na podstawie zapisanego profilu."""
    profile = load_profile()
    if profile is None:
        print("\n⚠ Brak profilu. Najpierw wybierz „Aktualizuj dane użytkownika”.")
        return

    location = profile.get("location", {})
    weather = None
    if location.get("lat") is not None and location.get("lon") is not None:
        weather = get_weather(location["lat"], location["lon"])

    env = Environment(loader=FileSystemLoader(str(BASE_DIR)))
    today = date.today().strftime("%Y-%m-%d")
    template = env.get_template("template.html")

    inspection_number = questionary.text("Podaj numer inspekcji:").ask()

    html_filled = template.render(
        apiary_name=profile["apiary_name"],
        beekeeper_name=profile["beekeeper_name"],
        veterinary_number=profile["veterinary_number"],
        location=location,
        weather=weather,
        inspection_number=inspection_number,
    )

    filename = f"Przegląd - {profile['apiary_name']} - {today}.pdf"
    INSPECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = INSPECTIONS_DIR / filename

    HTML(string=html_filled).write_pdf(output_path)
    print(f"\n✓ Plik zapisany: {output_path}")


# ── pętla główna ───────────────────────────────────────────────────────────────
def main() -> None:
    while True:
        action = questionary.select(
            "Co chcesz zrobić?",
            choices=[
                "Nowy przegląd",
                "Aktualizuj dane użytkownika",
                "Wyjście",
            ],
        ).ask()

        if action == "Nowy przegląd":
            new_inspection()
        elif action == "Aktualizuj dane użytkownika":
            update_user_data()
        else:  # "Wyjście" albo przerwanie (Ctrl+C / None)
            print("Do zobaczenia! 🐝")
            break


if __name__ == "__main__":
    main()
