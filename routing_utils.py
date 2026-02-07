from urllib.parse import urlencode

import streamlit as st

try:
    import requests  # type: ignore
except Exception:
    requests = None


_DOW_KR = ["월", "화", "수", "목", "금", "토", "일"]


def format_date_with_dow_kr(date_str: str) -> str:
    """'YYYY-MM-DD' -> 'YYYY-MM-DD(화)' """
    try:
        from datetime import datetime
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return f"{date_str}({_DOW_KR[d.weekday()]})"
    except Exception:
        return date_str


def _osrm_distance_m(lat1: float, lng1: float, lat2: float, lng2: float):
    """
    Road distance via OSRM demo server (driving).
    Returns meters(float) or None.
    """
    if not requests:
        return None
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}"
        params = {"overview": "false", "alternatives": "false", "steps": "false"}
        r = requests.get(url + "?" + urlencode(params), timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        routes = data.get("routes") or []
        if not routes:
            return None
        dist = routes[0].get("distance")
        if dist is None:
            return None
        return float(dist)
    except Exception:
        return None


def driving_km_between(p1: tuple[float, float], p2: tuple[float, float]):
    """Returns driving distance km between (lat,lng) pairs using OSRM demo server."""
    m = _osrm_distance_m(p1[0], p1[1], p2[0], p2[1])
    if m is None:
        return None
    return m / 1000.0


def compute_day_driving_km(day_items: list[dict]):
    """
    Returns (segment_km_list, total_km)
    - segment_km_list aligns with day_items: first is None, others are km from previous coord
    - total_km sums available segments (rounded 1 decimal)
    """
    try:
        from map_utils import get_coord_from_map_url
    except Exception:
        get_coord_from_map_url = None

    coords = []
    for it in day_items:
        url = (it.get("map_url") or "").strip()
        coord = get_coord_from_map_url(url) if get_coord_from_map_url else None
        coords.append(coord)

    seg = [None] * len(day_items)
    total = 0.0
    prev = None
    for i, coord in enumerate(coords):
        if coord and prev:
            km = driving_km_between(prev, coord)
            seg[i] = km
            if km is not None:
                total += float(km)
        if coord:
            prev = coord
    return seg, (round(total, 1) if total else 0.0)
