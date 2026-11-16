"""Address search and road routes. The outside services are replaced by fakes: tests must
never depend on (or load) someone else's server."""

import pytest

from app.core.config import get_settings
from app.services import geo_service
from tests.conftest import make_user

pytestmark = pytest.mark.anyio

NOMINATIM_ROWS = [
    {
        "name": "Technopark",
        "display_name": "Technopark, Kazhakkoottam, Thiruvananthapuram, Kerala, 695581, India",
        "lat": "8.5578269",
        "lon": "76.8807437",
    },
    {"display_name": "Mavoor Road, Kozhikode, Kerala, India", "lat": "11.2588", "lon": "75.7804"},
    {"display_name": "broken row without coordinates"},
]

OSRM_ROUTE = {
    "code": "Ok",
    "routes": [
        {
            "distance": 2126.4,
            "duration": 181.7,
            # GeoJSON order: longitude first.
            "geometry": {"coordinates": [[76.8735, 8.5686], [76.8760, 8.5600], [76.8790, 8.5520]]},
        }
    ],
}


@pytest.fixture
def outside(monkeypatch):
    """Fake map services; records every call that would have gone to the internet."""
    calls = []

    async def fake_get_json(url, params):
        calls.append((url, params))
        return OSRM_ROUTE if "/route/" in url else NOMINATIM_ROWS

    async def no_waiting():
        return None

    monkeypatch.setattr(geo_service, "_get_json", fake_get_json)
    monkeypatch.setattr(geo_service, "_wait_for_search_slot", no_waiting)
    # Fixed addresses, so the test means the same whatever a developer's .env says.
    monkeypatch.setattr(get_settings(), "geocoder_url", "https://geocoder.test/")
    monkeypatch.setattr(get_settings(), "geocoder_country_codes", "in")
    monkeypatch.setattr(get_settings(), "routing_url", "https://router.test")
    return calls


async def test_address_search_returns_clean_results_and_caches_them(client, outside):
    user = await make_user(client, "Searcher")
    params = {"q": "  Technopark   Phase 3 ", "near_lat": 8.56, "near_lng": 76.88}
    r = await client.get("/geo/search", params=params, headers=user)
    assert r.status_code == 200, r.text
    first, second = r.json()  # the broken row was dropped, not passed on
    assert first == {
        "label": "Technopark",
        "detail": "Kazhakkoottam, Thiruvananthapuram, Kerala",
        "lat": 8.5578269,
        "lng": 76.8807437,
    }
    assert second["label"] == "Mavoor Road" and second["detail"] == "Kozhikode, Kerala, India"

    url, sent = outside[0]
    assert url == "https://geocoder.test/search"
    assert sent["q"] == "Technopark Phase 3" and sent["countrycodes"] == "in"
    assert sent["viewbox"] == "76.4,9.1,77.4,8.1"  # "prefer results around here"

    # Same question from someone standing nearby: answered from the cache.
    again = await client.get("/geo/search", params={"q": "technopark phase 3", "near_lat": 8.57, "near_lng": 76.9}, headers=user)
    assert again.json() == r.json() and len(outside) == 1


async def test_search_needs_a_login_and_a_real_query(client, outside):
    assert (await client.get("/geo/search", params={"q": "Technopark"})).status_code == 401
    user = await make_user(client, "Shorty")
    assert (await client.get("/geo/search", params={"q": "ab"}, headers=user)).status_code == 422
    assert outside == []


async def test_road_route_gives_distance_time_and_a_line_for_the_map(client, outside):
    user = await make_user(client, "Router")
    params = {"from_lat": 8.56861, "from_lng": 76.87352, "to_lat": 8.55204, "to_lng": 76.87901}
    r = await client.get("/geo/route", params=params, headers=user)
    assert r.status_code == 200, r.text
    route = r.json()
    assert route["distance_m"] == 2126 and route["duration_s"] == 182
    assert route["points"][0] == [8.5686, 76.8735] and route["points"][-1] == [8.552, 76.879]  # lat first

    url, _ = outside[0]  # the service gets rounded positions, longitude first
    assert url == "https://router.test/route/v1/driving/76.8735,8.5686;76.879,8.552"
    await client.get("/geo/route", params=params, headers=user)
    assert len(outside) == 1  # cached


async def test_a_failing_or_disabled_service_gives_a_clear_503(client, monkeypatch):
    user = await make_user(client, "Unlucky")
    route = {"from_lat": 8.5, "from_lng": 76.9, "to_lat": 8.6, "to_lng": 76.8}

    async def no_route_found(url, params):
        return {"code": "NoRoute", "routes": []}

    monkeypatch.setattr(geo_service, "_get_json", no_route_found)
    r = await client.get("/geo/route", params=route, headers=user)
    assert r.status_code == 503 and "No road route" in r.json()["detail"]

    monkeypatch.setattr(get_settings(), "geocoder_url", "")
    monkeypatch.setattr(get_settings(), "routing_url", None)
    assert (await client.get("/geo/search", params={"q": "Anywhere"}, headers=user)).status_code == 503
    assert (await client.get("/geo/route", params=route, headers=user)).status_code == 503
