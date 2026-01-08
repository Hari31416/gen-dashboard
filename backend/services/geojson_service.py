"""
GeoJSON Service for Map Chart Generation.

Provides URL mappings and configuration for Indian geographic data files.
"""

import re
from typing import Dict, Optional

# Base URL for serving GeoJSON files (relative to static mount)
GEOJSON_BASE_URL = "/static/geojsons"

# State name to filename mapping (lowercase, underscore-separated)
STATE_FILENAME_MAP = {
    "andaman and nicobar islands": "andaman_nicobar_districts",
    "andaman & nicobar islands": "andaman_nicobar_districts",
    "andhra pradesh": "andhra_pradesh_districts",
    "arunachal pradesh": "arunachal_pradesh_districts",
    "assam": "assam_districts",
    "bihar": "bihar_districts",
    "chandigarh": "chandigarh_districts",
    "chhattisgarh": "chhattisgarh_districts",
    "dadra and nagar haveli and daman and diu": "daman_diu_districts",
    "daman and diu": "daman_diu_districts",
    "daman & diu": "daman_diu_districts",
    "delhi": "delhi_districts",
    "nct of delhi": "delhi_districts",
    "goa": "goa_districts",
    "gujarat": "gujarat_districts",
    "haryana": "haryana_districts",
    "himachal pradesh": "himachal_pradesh_districts",
    "jammu and kashmir": "jammu_kashmir_districts",
    "jammu & kashmir": "jammu_kashmir_districts",
    "jharkhand": "jharkhand_districts",
    "karnataka": "karnataka_districts",
    "kerala": "kerala_districts",
    "ladakh": "ladakh_districts",
    "lakshadweep": "lakshadweep_districts",
    "madhya pradesh": "madhya_pradesh_districts",
    "maharashtra": "maharashtra_districts",
    "manipur": "manipur_districts",
    "meghalaya": "meghalaya_districts",
    "mizoram": "mizoram_districts",
    "nagaland": "nagaland_districts",
    "odisha": "odisha_districts",
    "orissa": "odisha_districts",
    "puducherry": "puducherry_districts",
    "pondicherry": "puducherry_districts",
    "punjab": "punjab_districts",
    "rajasthan": "rajasthan_districts",
    "sikkim": "sikkim_districts",
    "tamil nadu": "tamil_nadu_districts",
    "telangana": "telangana_districts",
    "tripura": "tripura_districts",
    "uttar pradesh": "uttar_pradesh_districts",
    "uttarakhand": "uttarakhand_districts",
    "uttaranchal": "uttarakhand_districts",
    "west bengal": "west_bengal_districts",
}


def normalize_state_name(state_name: str) -> str:
    """Normalize state name for lookup."""
    return state_name.lower().strip()


def get_state_geojson_filename(state_name: str) -> Optional[str]:
    """
    Get the GeoJSON filename for a given state.

    Args:
        state_name: Name of the Indian state

    Returns:
        Filename (without .geojson extension) or None if not found
    """
    normalized = normalize_state_name(state_name)
    return STATE_FILENAME_MAP.get(normalized)


def get_geojson_config(
    level: str = "country", target_state: Optional[str] = None
) -> Dict[str, str]:
    """
    Get GeoJSON configuration for a geography level.

    Args:
        level: Geography level:
            - "country" or "india": India state-level map
            - "state": India district-level map (requires target_state)
            - "us" or "us_states": US state-level map
        target_state: Required when level is "state", name of the Indian state

    Returns:
        Dict with:
            - url: Full URL to GeoJSON file
            - feature_key: Property name in GeoJSON for matching (e.g., "STNAME")
            - lookup_key: How the feature key appears in lookup (e.g., "properties.STNAME")
    """
    # US states
    if level in ("us", "us_states", "united_states"):
        return {
            "url": f"{GEOJSON_BASE_URL}/us_states.geojson",
            "feature_key": "name",
            "lookup_key": "properties.name",
        }

    # World map (countries)
    if level in ("world", "global", "countries", "country"):
        # Use Natural Earth world countries GeoJSON from a public CDN
        return {
            "url": "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json",
            "feature_key": "name",
            "lookup_key": "properties.name",
            "format": "topojson",  # This is TopoJSON, not GeoJSON
            "feature": "countries",  # TopoJSON object name
        }

    # India country level (shows states)
    if level == "india" or level == "india_states":
        return {
            "url": f"{GEOJSON_BASE_URL}/india.geojson",
            "feature_key": "STNAME",
            "lookup_key": "properties.STNAME",
        }

    # India state level (shows districts)
    elif level == "state" and target_state:
        filename = get_state_geojson_filename(target_state)
        if filename:
            return {
                "url": f"{GEOJSON_BASE_URL}/{filename}.geojson",
                "feature_key": "dtname",
                "lookup_key": "properties.dtname",
            }
        else:
            # Fallback to country level if state not found
            return {
                "url": f"{GEOJSON_BASE_URL}/india.geojson",
                "feature_key": "STNAME",
                "lookup_key": "properties.STNAME",
            }

    # Default to world map
    return {
        "url": "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json",
        "feature_key": "name",
        "lookup_key": "properties.name",
        "format": "topojson",
        "feature": "countries",
    }


def get_available_states() -> list:
    """Return list of available states for district-level maps."""
    return sorted(set(STATE_FILENAME_MAP.values()))
