import json
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# Wczytanie konfiguracji
with open("config.json", "r") as f:
    config = json.load(f)

def send_telegram_message(message):
    token = config["telegram_token"]
    chat_id = config["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

def is_allowed_day(date_string):
    date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S")
    weekday = date.weekday()
    return weekday in config["allowed_weekdays"]

def is_after_time(date_string):
    date = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S")
    return date.time() >= datetime.strptime(config["earliest_time"], "%H:%M").time()

def run_bot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://portalpacjenta.luxmed.pl/PatientPortal/Account/LogIn")
        page.fill('input[name="Login"]', config["username"])
        page.fill('input[name="Password"]', config["password"])
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)

        page.goto("https://portalpacjenta.luxmed.pl/PatientPortal/Reservations/Reservation/Index")
        page.fill("#city-autocomplete", config["city"])
        page.fill("#service-autocomplete", config["service"])
        page.click("button#search-button")
        page.wait_for_timeout(5000)

        content = page.content()
        json_data = page.evaluate("() => window.__INITIAL_STATE__")

        found = False
        for offer in json_data.get("Reservation", {}).get("VisitOffers", []):
            visit_time = offer.get("StartDate")
            free = offer.get("IsInSubscription", False)
            if (visit_time >= config["earliest_date"]
                    and is_allowed_day(visit_time)
                    and is_after_time(visit_time)
                    and (not config["free_in_package"] or free)):
                link = "https://portalpacjenta.luxmed.pl/PatientPortal/Reservations/Reservation/Index"
                send_telegram_message(f"✅ Znalazłam termin! {visit_time}\n{link}")
                found = True
                if config["auto_book"]:
                    page.click(f"text={offer['DoctorName']}")
                    page.click("button.reserve-button")
                    send_telegram_message("📅 Wizyta została automatycznie zarezerwowana.")
                break

        if not found:
            send_telegram_message("❌ Nie znaleziono dostępnych terminów spełniających kryteria.")

        browser.close()

while True:
    try:
        run_bot()
    except Exception as e:
        send_telegram_message(f"❗ Wystąpił błąd: {e}")
    time.sleep(300)
