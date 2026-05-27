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


# ── dane matki (sekcja 1 · Matka) ─────────────────────────────────────────────
def collect_queen() -> dict:
    """Zbierz dane o matce zgodne z DTO sekcji 1 szablonu."""
    queen_status = questionary.select(
        "Status matki:",
        choices=[
            questionary.Choice("Widziana", value="seen"),
            questionary.Choice("Niewidziana, czerw OK", value="not_seen_brood_ok"),
            questionary.Choice("Brak matki", value="missing"),
        ],
    ).ask()

    queen_marked = questionary.confirm("Matka znakowana?", default=False).ask()
    queen_marker_color = ""
    if queen_marked:
        year_color = {
            "1": "white",
            "6": "white",
            "2": "yellow",
            "7": "yellow",
            "3": "red",
            "8": "red",
            "4": "green",
            "9": "green",
            "5": "blue",
            "0": "blue",
        }
        suggested = year_color[str(date.today().year)[-1]]
        queen_marker_color = questionary.select(
            "Kolor znakowania (wg ostatniej cyfry roku):",
            choices=[
                questionary.Choice("Biały (1, 6)", value="white"),
                questionary.Choice("Żółty (2, 7)", value="yellow"),
                questionary.Choice("Czerwony (3, 8)", value="red"),
                questionary.Choice("Zielony (4, 9)", value="green"),
                questionary.Choice("Niebieski (5, 0)", value="blue"),
            ],
            default=suggested,
        ).ask()

    queen_cells = questionary.select(
        "Mateczniki:",
        choices=[
            questionary.Choice("Brak", value="none"),
            questionary.Choice("Ratunkowe", value="emergency"),
            questionary.Choice("Rojowe", value="swarm"),
            questionary.Choice("Cicha wymiana", value="supersedure"),
        ],
    ).ask()

    queen_cells_count = 0
    if queen_cells != "none":
        queen_cells_count = int(
            questionary.text(
                "Liczba mateczników:",
                default="0",
                validate=lambda t: t.isdigit() or "Podaj liczbę całkowitą, np. 2",
            ).ask()
        )

    return {
        "queen_status": queen_status,
        "queen_marked": queen_marked,
        "queen_marker_color": queen_marker_color,
        "queen_cells": queen_cells,
        "queen_cells_count": queen_cells_count,
    }


# ── dane czerwiu (sekcja 2 · Czerw) ────────────────────────────────────────────
def collect_brood() -> dict:
    """Zbierz dane o czerwiu zgodne z DTO sekcji 2 szablonu."""
    brood_eggs = questionary.confirm(
        "Jaja (potwierdza matkę z ostatnich 3 dni)?", default=False
    ).ask()
    brood_open = questionary.confirm("Czerw otwarty (larwy)?", default=False).ask()
    brood_capped = questionary.confirm(
        "Czerw kryty (zasklepiony)?", default=False
    ).ask()
    brood_drone = questionary.confirm("Czerw trutowy?", default=False).ask()
    brood_pattern = int(
        questionary.select(
            "Zwartość czerwiu (1–5):",
            choices=["1", "2", "3", "4", "5"],
            default="3",
        ).ask()
    )

    return {
        "brood_eggs": brood_eggs,
        "brood_open": brood_open,
        "brood_capped": brood_capped,
        "brood_drone": brood_drone,
        "brood_pattern": brood_pattern,
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

    hive_number = questionary.text("Podaj numer ula:").ask()
    inspection_number = questionary.text("Podaj numer inspekcji:").ask()
    queen = collect_queen()
    brood = collect_brood()

    html_filled = template.render(
        apiary_name=profile["apiary_name"],
        beekeeper_name=profile["beekeeper_name"],
        veterinary_number=profile["veterinary_number"],
        location=location,
        weather=weather,
        hive_number=hive_number,
        inspection_number=inspection_number,
        inspection_date=today,
        queen=queen,
        brood=brood,
    )

    # filename = f"Przegląd - {profile['apiary_name']} - {today}.pdf"
    filename = f"{profile['apiary_name']}-Ul-{hive_number}-Przegląd-{inspection_number}-{today}.pdf"
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
        else:
            print("Do zobaczenia! 🐝")
            break


if __name__ == "__main__":
    main()
