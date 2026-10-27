import json
import re
import logging
from pathlib import Path
from django.db import transaction, DatabaseError

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CURRENCY_MAPPING_FILE = (
    BASE_DIR / "users" / "fixtures" / "country_currency_mapping.json"
)


def load_country_currency_mapping():
    """Load country to currency mapping from JSON file."""
    try:
        if not CURRENCY_MAPPING_FILE.exists():
            logger.error(f"Currency mapping file not found: {CURRENCY_MAPPING_FILE}")
            return {
                "uganda": "UGX",
                "kenya": "KES",
                "tanzania": "TZS",
                "default": "USD",
            }

        with open(CURRENCY_MAPPING_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        mapping = {}
        for key, value in data.get("country_currency_mapping", {}).items():
            if not key.startswith("//"):
                mapping[key] = value

        if "default" not in mapping:
            mapping["default"] = "USD"

        return mapping

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing currency mapping JSON: {e}")
        return {"default": "USD"}
    except Exception as e:
        logger.error(f"Unexpected error loading currency mapping: {e}")
        return {"default": "USD"}


_COUNTRY_CURRENCY_MAP = None


def get_country_currency_map():
    """Get the country currency mapping, caching it for performance."""
    global _COUNTRY_CURRENCY_MAP
    if _COUNTRY_CURRENCY_MAP is None:
        _COUNTRY_CURRENCY_MAP = load_country_currency_mapping()
    return _COUNTRY_CURRENCY_MAP


def extract_country_from_location(location_str):
    """Extract country name from location string."""
    if not location_str or not isinstance(location_str, str):
        return None

    location_lower = location_str.lower().strip()
    if not location_lower:
        return None

    mapping = get_country_currency_map()

    for country in mapping.keys():
        if country in location_lower:
            return country

    cleaned = re.sub(r"[^\w\s,]", " ", location_lower)
    words = cleaned.split()

    for i in range(len(words)):

        if words[i] in mapping:
            return words[i]

        if i < len(words) - 1:
            two_words = f"{words[i]} {words[i+1]}"
            if two_words in mapping:
                return two_words

        if i < len(words) - 2:
            three_words = f"{words[i]} {words[i+1]} {words[i+2]}"
            if three_words in mapping:
                return three_words

    return None


def get_currency_code_for_location(location_str):
    """Get currency code for a location string."""
    mapping = get_country_currency_map()

    country = extract_country_from_location(location_str)

    if country and country in mapping:
        return mapping[country]

    return mapping.get("default", "USD")


@transaction.atomic
def assign_default_currency_to_institution(institution):
    """
    Assign a default currency to institution based on location.
    """
    from system.models import SystemCurrency

    if institution.currency_id:
        return institution.currency

    location = getattr(institution, "location", "") or ""
    currency_code = get_currency_code_for_location(location)

    try:
        currency = SystemCurrency.objects.get(
            code=currency_code,
        )

        institution.currency = currency
        institution.save(update_fields=["currency"])

        logger.info(
            f"Assigned currency {currency_code} to institution {institution.id} based on location: {location}"
        )
        return currency

    except SystemCurrency.DoesNotExist:
        logger.warning(
            f"Currency {currency_code} not found for institution {institution.id}. Falling back to USD."
        )

        try:
            currency = SystemCurrency.objects.get(code="USD")
            institution.currency = currency
            institution.save(update_fields=["currency"])
            return currency
        except SystemCurrency.DoesNotExist:
            # Last resort - get any currency
            currency = SystemCurrency.objects.first()
            if currency:
                institution.currency = currency
                institution.save(update_fields=["currency"])
                logger.warning(
                    f"Assigned fallback currency {currency.code} to institution {institution.id}"
                )
                return currency
            else:
                logger.error(
                    f"No currencies found in SystemCurrency table for institution {institution.id}"
                )
                return None
    except DatabaseError as e:
        logger.error(
            f"Database error assigning currency to institution {institution.id}: {e}"
        )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error assigning currency to institution {institution.id}: {e}"
        )
        return None


def validate_currency_mapping():
    """Validate that all currencies in mapping exist in SystemCurrency."""
    from system.models import SystemCurrency

    mapping = get_country_currency_map()
    missing_currencies = []

    for country, currency_code in mapping.items():
        if not country.startswith("//") and country != "default":
            exists = SystemCurrency.objects.filter(
                code=currency_code,
            ).exists()
            if not exists:
                missing_currencies.append((country, currency_code))

    return missing_currencies
