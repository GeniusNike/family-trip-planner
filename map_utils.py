from typing import Optional

import re
from urllib.parse import urlparse, parse_qs, unquote

import streamlit as st

try:
    import requests  # type: ignore
except Exception:
    requests = None


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def _resolve_short_url_cached(url: str) -> str:
    return _resolve_short_url(url)


def _resolve_short_url(url: str) -> str:
    """
    Resolve maps.app.goo.gl / goo.gl/maps short links to the final expanded URL.
    """
    if not url or not requests:
        return url
    try:
        resp = requests.get(url, allow_redirects=True, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        return resp.url or url
    except Exception:
        return url

try:
    from geopy.geocoders import Nominatim  # type: ignore
except Exception:
    Nominatim = None


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


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def _geocode_address_cached(addr: str):
    return _geocode_address(addr)


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

    # Resolve Google short links (maps.app.goo.gl / goo.gl) to expanded URL
    try:
        parsed0 = urlparse(u)
        host0 = (parsed0.netloc or '').lower()
        if host0.endswith('maps.app.goo.gl') or host0.endswith('goo.gl'):
            u = _resolve_short_url_cached(u)
    except Exception:
        pass

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


def get_coord_from_map_url(map_url: str):
    """Return (lat,lng) if possible; supports google maps links or address text."""
    parsed = extract_latlng_from_google_maps_url(map_url)
    if not parsed:
        return None
    kind, val = parsed
    if kind == "latlng":
        return val
    if kind == "addr":
        return _geocode_address_cached(val)
    return None


def collect_day_points(day_items: list[dict]):
    """Collect (lat,lng,title) list from schedule items."""
    pts = []
    for it in day_items:
        title = (it.get("title") or "").strip() or "장소"
        map_url = (it.get("map_url") or "").strip()
        if not map_url:
            continue

        parsed = extract_latlng_from_google_maps_url(map_url)
        if not parsed:
            continue
        kind, val = parsed
        if kind == "latlng":
            lat, lng = val
            pts.append((lat, lng, title))
            continue
        if kind == "addr":
            coord = _geocode_address_cached(val)
            if coord:
                lat, lng = coord
                pts.append((lat, lng, title))
    return pts


def render_day_map(day_items: list[dict], height: int = 520, **kwargs):
    """
    Render a big map with numbered markers (1,2,3...) and fit bounds.

    ⚠️ Streamlit Cloud/브라우저/패키지 조합에 따라 streamlit-folium이 빈 화면을 만드는 경우가 있어서,
    기본은 Folium HTML(iframe) 임베딩으로 렌더링하고, 가능하면 streamlit-folium도 시도합니다.

    kwargs:
      - key: (optional) unique key to avoid multi-map collisions
    """
    key: Optional[str] = kwargs.get("key")

    # Folium import (required)
    try:
        import folium  # type: ignore
        from folium.features import DivIcon  # type: ignore
    except Exception:
        st.error("지도 표시를 위해 folium 패키지가 필요해요. requirements.txt를 확인해 주세요.")
        return

    pts = collect_day_points(day_items)
    st.caption(f"지도 포인트: {len(pts)}개")  # 작은 디버그 힌트(사용자에게도 도움)

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

    # 1) Try streamlit-folium (some envs render better), but NEVER fail silently.
    rendered = False
    try:
        from streamlit_folium import st_folium  # type: ignore

        try:
            # Some versions accept key; some don't.
            st_folium(m, width=None, height=height, key=key)
        except TypeError:
            st_folium(m, width=None, height=height)
        rendered = True
    except Exception:
        rendered = False

    # 2) Fallback: embed Folium HTML (reliable when st_folium glitches)
    if not rendered:
        try:
            import streamlit.components.v1 as components  # type: ignore
            html = m.get_root().render()
            components.html(html, height=height, scrolling=False)
        except Exception:
            st.error("지도 렌더링 중 문제가 발생했어요. (folium/leaflet 리소스 차단 가능성도 있어요)")
            return


def _get_coord_from_map_url_uncached(map_url: str):
    """
    Uncached coordinate extraction.

    Returns (lat,lng) if 가능한 경우.
    - short link resolve (maps.app.goo.gl) handled inside extract_latlng_from_google_maps_url via _resolve_short_url
    - address geocoding via Nominatim (best-effort)
    """
    if not map_url:
        return None
    info = extract_latlng_from_google_maps_url(map_url)
    if not info:
        return None
    kind, val = info
    if kind == "latlng":
        return val
    if kind == "addr":
        return _geocode_address(val)
    return None


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 30)
def get_coord_from_map_url(map_url: str):
    """Cached wrapper for coordinate extraction to speed up schedule view."""
    return _get_coord_from_map_url_uncached(map_url)