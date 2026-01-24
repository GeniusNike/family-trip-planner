import re
from urllib.parse import urlparse, parse_qs, unquote

import streamlit as st

try:
    from geopy.geocoders import Nominatim  # type: ignore
except Exception:
    Nominatim = None


@st.cache_data(show_spinner=False)
def _geocode_address(addr: str):
    """Geocode with OpenStreetMap Nominatim (best-effort). Cached to avoid rate limits."""
    if not addr or not Nominatim:
        return None
    try:
        geolocator = Nominatim(user_agent="family-trip-planner")
        loc = geolocator.geocode(addr, language="ko")
        if loc:
            return (float(loc.latitude), float(loc.longitude))
    except Exception:
        return None
    return None


def extract_latlng_from_google_maps_url(url: str):
    """
    Best-effort extraction:
    - URLs containing '@lat,lng,' pattern
    - query params q=lat,lng or query=lat,lng
    - query params q=<address> -> returns ('addr', address) for geocoding
    Returns:
      - ('latlng', (lat,lng)) or ('addr', '...') or None
    """
    if not url:
        return None
    u = url.strip()

    m = re.search(r"@(-?\d+\.\d+),\s*(-?\d+\.\d+)", u)
    if m:
        return ("latlng", (float(m.group(1)), float(m.group(2))))

    try:
        parsed = urlparse(u)
        qs = parse_qs(parsed.query)
        for key in ("q", "query"):
            if key in qs and qs[key]:
                v = unquote(qs[key][0]).strip()
                m2 = re.match(r"^\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*$", v)
                if m2:
                    return ("latlng", (float(m2.group(1)), float(m2.group(2))))
                if v:
                    return ("addr", v)
    except Exception:
        pass

    m3 = re.search(r"/search/([^/]+)", u)
    if m3:
        v = unquote(m3.group(1)).replace("+", " ").strip()
        m3b = re.match(r"^\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*$", v)
        if m3b:
            return ("latlng", (float(m3b.group(1)), float(m3b.group(2))))
        if v:
            return ("addr", v)

    return None


def collect_day_points(day_items: list[dict]):
    """Collect (lat,lng,title) list from schedule items."""
    pts = []
    for it in day_items:
        title = (it.get("title") or "").strip() or "장소"
        map_url = (it.get("map_url") or "").strip()
        if not map_url:
            continue

        info = extract_latlng_from_google_maps_url(map_url)
        if not info:
            continue
        kind, val = info
        if kind == "latlng":
            lat, lng = val
            pts.append((lat, lng, title))
        elif kind == "addr":
            coord = _geocode_address(val)
            if coord:
                lat, lng = coord
                pts.append((lat, lng, title))
    return pts


def render_day_map(day_items: list[dict], height: int = 520):
    """
    Render a big map with numbered markers (1,2,3...) and fit bounds.
    Uses Folium + streamlit-folium.
    """
    try:
        import folium  # type: ignore
        from folium.features import DivIcon  # type: ignore
        from streamlit_folium import st_folium  # type: ignore
    except Exception:
        st.error("지도 표시를 위해 folium / streamlit-folium 패키지가 필요해요. requirements.txt를 업데이트해 주세요.")
        return

    pts = collect_day_points(day_items)
    if len(pts) == 0:
        st.info(
            "이 날의 일정에서 좌표를 읽을 수 있는 Google 지도 링크가 없어요.\n\n"
            "팁: Google 지도에서 '공유 → 링크 복사'로 나온 URL을 넣으면 대부분 @lat,lng 형태로 저장돼요."
        )
        return

    avg_lat = sum(p[0] for p in pts) / len(pts)
    avg_lng = sum(p[1] for p in pts) / len(pts)

    m = folium.Map(location=[avg_lat, avg_lng], zoom_start=12, control_scale=True)

    bounds = []
    for idx, (lat, lng, title) in enumerate(pts, start=1):
        bounds.append((lat, lng))
        folium.Marker(
            location=[lat, lng],
            tooltip=f"{idx}. {title}",
            icon=DivIcon(
                icon_size=(28, 28),
                icon_anchor=(14, 14),
                html=f"""
                <div style="
                    width:28px;height:28px;border-radius:14px;
                    background:#1f6feb;color:white;
                    display:flex;align-items:center;justify-content:center;
                    font-weight:800;font-size:14px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.35);
                ">{idx}</div>
                """,
            ),
        ).add_to(m)

    if len(bounds) >= 2:
        m.fit_bounds(bounds, padding=(30, 30))

    st_folium(m, width=None, height=height)
