from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app

OWNER = {"X-User-Id": "owner"}
ALICE = {"X-User-Id": "alice"}
NEW_EVENT = {"name": "Event1", "availableTickets": 400, "eventDate": "2123-01-04T20:00:00Z"}


@pytest.fixture
def client() -> TestClient:
    # raise_server_exceptions=False so a 500 comes back as a response instead of being re-raised.
    return TestClient(create_app(), raise_server_exceptions=False)


def create_event(client, payload=None, headers=OWNER) -> dict:
    response = client.post("/api/v1/events", json=payload or NEW_EVENT, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def assert_problem(response, status: int, code: str) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == status
    assert body["code"] == code
    assert body["type"] == "/problems/" + code.replace("_", "-")
    assert body["title"] and body["detail"] and body["instance"]
    return body


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- auth ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("headers", [{}, {"X-User-Id": "   "}])
def test_missing_or_blank_user_id_is_401(client, headers):
    assert_problem(client.get("/api/v1/events", headers=headers), 401, "unauthorized")


def test_non_owner_cannot_create_event(client):
    assert_problem(client.post("/api/v1/events", json=NEW_EVENT, headers=ALICE), 403, "forbidden")


def test_non_owner_cannot_cancel_or_see_stats(client):
    event = create_event(client)
    assert_problem(client.delete(f"/api/v1/events/{event['id']}", headers=ALICE), 403, "forbidden")
    assert_problem(client.get(f"/api/v1/events/{event['id']}/stats", headers=ALICE), 403, "forbidden")


def test_owner_cannot_touch_another_owners_event(client, monkeypatch):
    monkeypatch.setattr(config, "OWNER_IDS", frozenset({"owner", "owner2"}))
    event = create_event(client)
    other = {"X-User-Id": "owner2"}
    assert_problem(client.delete(f"/api/v1/events/{event['id']}", headers=other), 403, "forbidden")
    assert_problem(client.get(f"/api/v1/events/{event['id']}/stats", headers=other), 403, "forbidden")


# --- events -------------------------------------------------------------------------------------

def test_create_event_returns_201_location_and_camel_case(client):
    response = client.post("/api/v1/events", json=NEW_EVENT, headers=OWNER)
    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/api/v1/events/{body['id']}"
    assert body == {"id": 1, "name": "Event1", "availableTickets": 400, "eventDate": "2123-01-04T20:00:00Z"}


def test_list_events_shows_available_tickets(client):
    event = create_event(client)
    client.post(f"/api/v1/events/{event['id']}/tickets", json={"quantity": 3}, headers=ALICE)
    listed = client.get("/api/v1/events", headers=ALICE).json()
    assert [(e["name"], e["availableTickets"]) for e in listed] == [("Event1", 397)]


def test_create_event_in_the_past_is_400(client):
    payload = {**NEW_EVENT, "eventDate": "2000-01-01T00:00:00Z"}
    body = assert_problem(client.post("/api/v1/events", json=payload, headers=OWNER), 400, "validation_error")
    assert "future" in body["detail"]


def test_invalid_body_is_400_with_field_errors(client):
    response = client.post("/api/v1/events", json={"name": "x", "availableTickets": "many"}, headers=OWNER)
    body = assert_problem(response, 400, "validation_error")
    fields = {e["field"] for e in body["errors"]}
    assert fields == {"availableTickets", "eventDate"}


# --- tickets ------------------------------------------------------------------------------------

def test_book_ticket_defaults_to_quantity_1(client):
    event = create_event(client)
    response = client.post(f"/api/v1/events/{event['id']}/tickets", headers=ALICE)
    assert response.status_code == 201
    body = response.json()
    assert (body["eventId"], body["userId"], body["quantity"], body["status"]) == (event["id"], "alice", 1, "ACTIVE")


def test_booking_more_than_available_is_409(client):
    event = create_event(client, {**NEW_EVENT, "availableTickets": 1})
    response = client.post(f"/api/v1/events/{event['id']}/tickets", json={"quantity": 2}, headers=ALICE)
    body = assert_problem(response, 409, "sold_out")
    assert body["instance"] == f"/api/v1/events/{event['id']}/tickets"


def test_booking_invalid_quantity_is_400(client):
    event = create_event(client)
    response = client.post(f"/api/v1/events/{event['id']}/tickets", json={"quantity": 11}, headers=ALICE)
    assert_problem(response, 400, "validation_error")


def test_booking_unknown_event_is_404(client):
    assert_problem(client.post("/api/v1/events/99/tickets", headers=ALICE), 404, "event_not_found")


def test_non_numeric_event_id_is_400(client):
    assert_problem(client.post("/api/v1/events/abc/tickets", headers=ALICE), 400, "validation_error")


def test_my_tickets_only_shows_own_tickets(client):
    event = create_event(client)
    client.post(f"/api/v1/events/{event['id']}/tickets", headers=ALICE)
    client.post(f"/api/v1/events/{event['id']}/tickets", headers={"X-User-Id": "bob"})
    mine = client.get("/api/v1/tickets", headers=ALICE).json()
    assert [t["userId"] for t in mine] == ["alice"]


# --- owner: stats and cancel --------------------------------------------------------------------

def test_stats(client):
    event = create_event(client)
    client.post(f"/api/v1/events/{event['id']}/tickets", json={"quantity": 5}, headers=ALICE)
    response = client.get(f"/api/v1/events/{event['id']}/stats", headers=OWNER)
    assert response.status_code == 200
    assert response.json() == {"capacity": 400, "booked": 5, "available": 395}


def test_stats_unknown_event_is_404(client):
    assert_problem(client.get("/api/v1/events/99/stats", headers=OWNER), 404, "event_not_found")


def test_cancel_event_is_soft_and_idempotent(client):
    event = create_event(client)
    url = f"/api/v1/events/{event['id']}"
    client.post(f"{url}/tickets", json={"quantity": 2}, headers=ALICE)

    assert client.delete(url, headers=OWNER).status_code == 204
    assert client.delete(url, headers=OWNER).status_code == 204  # repeating is safe

    assert client.get("/api/v1/events", headers=ALICE).json() == []
    assert [t["status"] for t in client.get("/api/v1/tickets", headers=ALICE).json()] == ["CANCELLED"]
    assert client.get(f"{url}/stats", headers=OWNER).json()["booked"] == 2  # sales history is kept
    assert_problem(client.post(f"{url}/tickets", headers=ALICE), 404, "event_not_found")


def test_cancel_past_event_is_409():
    now = [datetime.now(timezone.utc)]
    client = TestClient(create_app(clock=lambda: now[0]), raise_server_exceptions=False)
    event = create_event(client)
    now[0] = datetime(2200, 1, 1, tzinfo=timezone.utc)  # time passes, the event took place
    response = client.delete(f"/api/v1/events/{event['id']}", headers=OWNER)
    assert_problem(response, 409, "event_already_took_place")


def test_cancel_unknown_event_is_404(client):
    assert_problem(client.delete("/api/v1/events/99", headers=OWNER), 404, "event_not_found")


# --- framework and unexpected errors ------------------------------------------------------------

def test_unknown_route_is_problem_json(client):
    assert_problem(client.get("/api/v1/nope"), 404, "not_found")


def test_wrong_method_is_problem_json(client):
    assert_problem(client.put("/api/v1/events", headers=OWNER), 405, "method_not_allowed")


def test_openapi_documents_400_not_422(client):
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/api/v1/events/{event_id}/tickets"]["post"]["responses"]
    assert {"201", "400", "401", "404", "409"} <= set(responses)
    assert "422" not in responses
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_unexpected_error_is_500_without_leaking_details():
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    body = assert_problem(response, 500, "internal_error")
    assert "secret" not in response.text
    assert body["detail"] == "An unexpected error occurred."
