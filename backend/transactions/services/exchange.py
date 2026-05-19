import requests
from django.conf import settings
from django.core.cache import cache


def get_xaf_rates() -> dict:
    """
    Returns XAF exchange rates. Cached for 1 hour to save API calls.
    Free tier: 1,500 requests/month.
    """
    cached = cache.get("xaf_rates")
    if cached:
        return cached

    response = requests.get(
        f"https://v6.exchangerate-api.com/v6/{settings.EXCHANGE_API_KEY}/latest/XAF"
    )
    data = response.json()

    rates = {
        "USD": data["conversion_rates"].get("USD"),
        "EUR": data["conversion_rates"].get("EUR"),
        "GBP": data["conversion_rates"].get("GBP"),
    }

    cache.set("xaf_rates", rates, timeout=3600)  # cache 1 hour
    return rates