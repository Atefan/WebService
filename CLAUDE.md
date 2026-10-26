# STACKIT Coding Challenge: Event Ticket Booking Service

This file is the full context from the planning session. Read all of it before doing anything.

## Working mode
- The user is new to Java/Go, comfortable enough with Python, and has a hard time budget (~2 hours; the sheet says 3h).
- **At the start of the session, ask the user** whether you should (A) scaffold the whole skeleton and implement, or (B) coach step by step while they type the code. Do not assume.
- Follow the global rules in `~/.claude/CLAUDE.md`: ask when ambiguous, never `git push`, show a diff before committing, no attribution lines in commits.
- Keep it simple. No DI framework, no event bus, no abstract base classes, no gold-plating. Readable beats clever.
- Windows 11, PowerShell. Python 3.12 is installed. Docker is NOT installed. VS Code is the editor.

## The challenge (from the printed sheet)
Goal: demonstrate problem-solving within constraints. Not about completeness, but about a thoughtful approach.
Use a web framework you know (Spring / Spring Boot excluded). Language is free.

RESTful web service where a user books tickets for an event, and an owner maintains events.
No user management: identify the user by simply passing a user id. Mark future improvements with `# TODO:` comments.

**User can:** see all available events, book a ticket for an event, see all their booked tickets.
**Event service owner can:** add new events, delete events, see how many tickets are booked for a specific event.

**Non-technical:** code is structured, easy to read and extendable. README with: how to run the service, how to send a few example requests, any assumptions made.

**Example event object** (types not required, can change):
```json
{ "name": "Event1", "availableTickets": 400, "eventDate": "04.01.2123" }
```
**Additional features:** optional; document them briefly in the README.
**Relevant for review:** API design, code structure (easy to understand, easy to add requirements), code quality.
**Time:** 3 hours on the sheet. **Submission:** by email (address is on the sheet).

## Decisions made
- **Language/stack:** Python 3.12 + FastAPI + Uvicorn. Pydantic for schemas. pytest + httpx for tests. Swagger UI at `/docs` is the free interactive client.
- **Storage:** in-memory behind repository interfaces (swap for a DB later).
- **No client app.** The "client" is `requests.http` (VS Code REST Client / JetBrains format), curl examples in the README, and `/docs`.
- **Users are not stored.** A user is just the string in the `X-User-Id` header.
- **Roles are derived, not stored:** `OWNER_IDS` env var (comma-separated, default `owner`). `is_owner = user_id in OWNER_IDS`.
- **Per-event ownership:** `Event.owner_id` is set on create. Only that owner can delete the event or see its stats.
  Role check (is an owner at all) lives in `api/deps.py`; ownership check (is *their* event) lives in the domain/service. Both return 403.
- **Delete = soft delete (cancel).** `DELETE /events/{id}` marks the event `CANCELLED` and marks all its tickets `CANCELLED`. Nothing is erased.
- **Ticket has a status** (`ACTIVE` | `CANCELLED`) so users can see their ticket's event was cancelled.
- **Dates:** ISO-8601 on the wire (the sample `04.01.2123` is ambiguous). Timezone-aware UTC internally; naive input is treated as UTC. Reject past dates on create.
- **Versioned URLs:** everything under `/api/v1`.

## Architecture: layered / ports and adapters (light)
```
api/            HTTP adapter: routes, Pydantic schemas, auth deps, error mapping. Only layer that knows HTTP/JSON.
application/    Use cases (EventService, BookingService) + ports.py (Protocol interfaces). Orchestrates; no HTTP, no storage details.
domain/         Event, Ticket, enums, domain errors, business invariants. Imports nothing from the project.
infrastructure/ In-memory repository implementations of the ports.
main.py         Composition root: create_app() builds repos, lock, clock, services, router. Manual DI.
```
**Dependency rule:** imports point inward only. `api -> application -> domain`; `infrastructure -> application.ports + domain`. Application never imports infrastructure.

### Folder structure
```
ticket-service/   (this folder)
├─ CLAUDE.md  README.md  requirements.txt  requests.http
├─ app/
│  ├─ __init__.py
│  ├─ main.py              create_app(): wiring
│  ├─ config.py            OWNER_IDS, MAX_TICKETS_PER_BOOKING from env
│  ├─ domain/              models.py (Event, Ticket, EventStatus, TicketStatus), errors.py
│  ├─ application/         ports.py, event_service.py, booking_service.py
│  ├─ infrastructure/      in_memory_repos.py
│  └─ api/                 routes.py, schemas.py, deps.py, errors.py
├─ scripts/                demo_concurrency.py   (extra: visible proof of no overselling)
└─ tests/                  test_booking.py, test_events.py, test_concurrency.py, test_api.py
```

## Domain model
```python
class EventStatus(str, Enum): ACTIVE, CANCELLED
class TicketStatus(str, Enum): ACTIVE, CANCELLED

@dataclass
class Event:
    id: int | None
    owner_id: str
    name: str
    capacity: int
    event_date: datetime
    booked: int = 0
    status: EventStatus = EventStatus.ACTIVE
    available -> capacity - booked                      # derived, never stored
    book(qty)    # if status != ACTIVE: raise EventNotFound; if qty > available: raise SoldOut; booked += qty
    cancel()     # status = CANCELLED (booked count is kept so the owner still sees what was sold)
    ensure_owned_by(user_id)  # raise Forbidden if owner_id differs

@dataclass
class Ticket:
    id: int | None
    event_id: int
    user_id: str
    quantity: int
    booked_at: datetime
    status: TicketStatus = TicketStatus.ACTIVE
    cancel()
```
Domain errors (no HTTP knowledge): `DomainError` base; `EventNotFound`, `SoldOut`, `ValidationError`, `Forbidden`, `Unauthorized`.

## Ports (application/ports.py, typing.Protocol)
- `EventRepository`: `add(event) -> Event`, `get(id) -> Event | None`, `list_all() -> list[Event]`, `save(event) -> None`
- `TicketRepository`: `add(ticket) -> Ticket`, `list_by_user(user_id)`, `list_by_event(event_id)`, `cancel_by_event(event_id) -> int`
- Clock: `Callable[[], datetime]`, injected; default `datetime.now(timezone.utc)`. Makes "upcoming" and "past date" testable.

## Services (application/)
**EventService** (takes events repo, tickets repo, clock, shared lock)
- `create(user_id, name, capacity, event_date)`: validate capacity > 0, name non-empty, date in future; `Event(owner_id=user_id)`; add.
- `list_upcoming()`: status ACTIVE and `event_date > now`. Sold-out events are still listed with `availableTickets: 0`.
- `cancel(user_id, event_id)` (HTTP DELETE): under lock: get (404 if missing), `ensure_owned_by`, if already CANCELLED no-op (idempotent, still 204), else `event.cancel()`, save, `tickets.cancel_by_event(event_id)`.
- `stats(user_id, event_id)`: get (404), `ensure_owned_by`, return capacity / booked / available. Works for cancelled events too.

**BookingService**
- `book(user_id, event_id, qty)`: validate 1 <= qty <= MAX_TICKETS_PER_BOOKING (default 10); under the shared lock: get (404), event date still in future, `event.book(qty)`, `events.save(event)`, `tickets.add(Ticket(...))`.
- `tickets_of(user_id)`: all tickets of that user, including their status.

### Concurrency (important, and the "senior" signal)
FastAPI runs plain `def` handlers in a threadpool, so requests really run in parallel. Booking is check-then-act, so without a lock two requests can both see 1 ticket left and oversell. Booking and cancelling also race: a booking could slip in after cancel marked the tickets and leave an ACTIVE ticket on a cancelled event.
- Solution: **one shared `threading.RLock`**, created in `create_app()`, passed to both services. Compound operations (`book`, `cancel`) run entirely inside `with lock:`.
- Repos are individually thread-safe (their own small lock for id generation / dict mutation) but do not know about the workflow lock.
- The lock is an in-process stand-in for a DB transaction. Document this honestly.
- Limit: only correct in a single process. Multiple uvicorn workers or instances need a DB transaction (e.g. `UPDATE events SET booked = booked + :q WHERE id = :id AND booked + :q <= capacity`, or `SELECT ... FOR UPDATE`). Put a `# TODO:` where this applies.

## API (all under `/api/v1`, identity via `X-User-Id` header)
| Who | Endpoint | Behavior |
|---|---|---|
| any | `GET /health` | liveness |
| user | `GET /events` | upcoming, ACTIVE events with `availableTickets` |
| user | `POST /events/{id}/tickets` | body `{"quantity": 1}` (default 1). 201 + TicketOut. 404 unknown/cancelled event, 409 sold out / not enough, 400 invalid qty |
| user | `GET /tickets` | caller's tickets, each with `status` (ACTIVE/CANCELLED) |
| owner | `POST /events` | body `{name, availableTickets/capacity, eventDate}`. 201 + `Location: /api/v1/events/{id}` |
| owner (own event) | `DELETE /events/{id}` | soft delete/cancel. 204 (idempotent). 404 unknown, 403 not yours |
| owner (own event) | `GET /events/{id}/stats` | `{capacity, booked, available}` |

Use camelCase on the wire (`eventDate`, `availableTickets`) via a Pydantic alias generator. Keep the sample's field names where possible; accept `availableTickets` as the initial capacity on create (decide and document in README).

### Auth (api/deps.py)
- `get_caller`: reads `X-User-Id`; missing/blank -> 401. Returns `Caller(user_id, is_owner)` (frozen dataclass).
- `require_owner`: `Depends` that returns 403 unless `caller.is_owner`.
- Services only ever receive `user_id` (a plain string).

### Errors (api/errors.py): RFC 7807 Problem Details (chosen extra)
Every error response uses `Content-Type: application/problem+json` and this body (RFC 7807, since superseded by RFC 9457 with the same format; mention in README):
```json
{
  "type": "/problems/sold-out",
  "title": "Not enough tickets left",
  "status": 409,
  "detail": "Event 7 has only 1 ticket(s) left, requested 2.",
  "instance": "/api/v1/events/7/tickets",
  "code": "sold_out"
}
```
`type` is a relative problem URI (not served; note in README that a real service would host docs there). `code` is a stable machine-readable extension member. `instance` is the request path.
| Domain error | HTTP | code | type | title |
|---|---|---|---|---|
| ValidationError | 400 | validation_error | /problems/validation-error | Invalid request |
| Unauthorized | 401 | unauthorized | /problems/unauthorized | Missing or empty X-User-Id header |
| Forbidden | 403 | forbidden | /problems/forbidden | Not allowed |
| EventNotFound | 404 | event_not_found | /problems/event-not-found | Event not found |
| SoldOut | 409 | sold_out | /problems/sold-out | Not enough tickets left |
Override FastAPI's default 422 request-validation handler: return 400 in the same Problem Details shape, plus an extension member `errors: [{"field": "...", "message": "..."}]`. Also add a catch-all handler for unexpected exceptions returning 500 as Problem Details without leaking internals.
Keep one small helper `problem(status, code, title, detail, instance) -> JSONResponse` so the format lives in exactly one place.
Domain exceptions bubble up untouched through the layers (no try/except in between); they are mapped only at the edge. The domain errors carry a message (the `detail`), never HTTP knowledge.

### OpenAPI documentation (chosen extra)
Make `/docs` self-explanatory for reviewers:
- App metadata: title, version, description (include the `X-User-Id` / owner convention and a link to README assumptions); tags `events`, `tickets`, `owner` with descriptions.
- Every route: `summary`, `description`, and `responses={...}` documenting the Problem Details status codes (400/401/403/404/409) with example bodies.
- Pydantic schemas: `Field(description=..., examples=[...])` on every field and `model_config` / `json_schema_extra` with a full example object (e.g. `{"name": "Event1", "availableTickets": 400, "eventDate": "2123-01-04T20:00:00Z"}`).
- Document the `X-User-Id` header as a reusable `Header(..., description="...", examples=["alice"])` parameter on the dependency so it appears on every route in Swagger UI.
Keep descriptions short and factual.

### Concurrency demo script (chosen extra): scripts/demo_concurrency.py
A standalone script (uses `httpx` + `ThreadPoolExecutor`, no extra deps) that talks to a RUNNING server (`--base-url`, default `http://127.0.0.1:8000`):
1. Creates an event with capacity 50 as the owner (`X-User-Id: owner`).
2. Fires 200 parallel `POST /events/{id}/tickets` requests as different users.
3. Reads `GET /events/{id}/stats` and prints a summary, e.g. `booked 50 | rejected (409) 150 | oversold 0  -> PASS`.
Exit code non-zero if oversold != 0 or booked != capacity. Document usage in the README ("start the server, then run `python scripts/demo_concurrency.py`"). This is the first thing to cut if time runs out.

## Data flow
`JSON -> Pydantic schema (api) -> primitives (service args) -> domain objects -> repo storage`, and back the same way. Pydantic lives only in `api/`. Identity travels as `X-User-Id` header -> `Caller` -> plain `user_id`.

Sequence, book a ticket: `Client -> deps(Caller) -> schema validation -> route -> BookingService.book -> [lock] events.get -> date check -> event.book(qty) -> events.save -> tickets.add -> [unlock] -> 201 TicketOut`. SoldOut raised by the domain bubbles to `api/errors.py` -> 409.
Sequence, delete: `Client -> require_owner -> route -> EventService.cancel -> [lock] get -> ensure_owned_by -> event.cancel -> save -> tickets.cancel_by_event -> [unlock] -> 204`.

## Tests (pytest, keep few but meaningful)
- Unit (services with in-memory repos and a fixed clock): book happy path, quantity > available -> SoldOut, book cancelled/unknown event -> 404, past event -> rejected, create validation, cancel marks event and tickets CANCELLED, cancel by non-owner -> Forbidden, cancel idempotent, stats numbers, list excludes cancelled and past events.
- **Concurrency:** 50 threads each book 1 ticket of a 10-capacity event -> exactly 10 succeed, 40 get SoldOut, `event.booked == 10`, 10 tickets stored.
- Optional race test: concurrent book + cancel -> afterwards no ACTIVE ticket exists on the cancelled event.
- API tests with `fastapi.testclient.TestClient`: auth 401/403, status codes, camelCase fields, and that every error is `application/problem+json` with `type/title/status/detail/code` (including the 400 for invalid bodies and 404 for an unknown event).

## Execution plan (budget 2h, 15 min buffer)
| Time | Step |
|---|---|
| 0:00-0:10 | venv, install, `GET /health`, open `/docs`. **Checkpoint:** Swagger UI works. If not working by 10 min, stop and reassess. Also create the README skeleton and note assumptions in it as decisions are made. |
| 0:10-0:25 | domain: models + errors |
| 0:25-0:40 | ports + in-memory repos |
| 0:40-1:00 | services (with shared lock + clock) |
| 1:00-1:30 | api: schemas (with OpenAPI examples), deps, Problem Details errors, routes, `main.py` wiring |
| 1:30-1:45 | tests (incl. concurrency and Problem Details shape) |
| 1:45-1:55 | `scripts/demo_concurrency.py` (first thing to cut if behind) |
| 1:55-2:10 | final README pass, `requests.http`, TODO comments, run once from a fresh venv |

The sheet allows 3 hours, so 2h10 leaves slack. Rule: **no extras until the core tests pass.** Order of cutting if behind: demo script, then OpenAPI examples (keep summaries), never the tests or README.

Build vertical slices: `GET /events` and `POST /events` first, then booking, then my tickets, then stats and delete.

Setup commands:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn pytest httpx
pip freeze > requirements.txt   # or hand-write a short requirements.txt
uvicorn app.main:app --reload   # run
pytest                          # test
```

## README must contain
1. Short description + architecture overview (layers, why).
2. How to run (venv, install, uvicorn, `/docs`, env vars `OWNER_IDS`, `MAX_TICKETS_PER_BOOKING`) and how to run tests.
3. A few example requests (curl and/or `requests.http`): list events, create event as owner, book ticket, my tickets, stats, delete.
4. **Assumptions:** identity via `X-User-Id`, no authentication; owner = ids in `OWNER_IDS`; per-event ownership; "available" = ACTIVE and future date, sold-out still listed with 0; soft delete cancels event and tickets, idempotent; booking cancelled event -> 404; ISO-8601 dates (naive = UTC), past dates rejected; quantity per booking default 1, max 10; in-memory storage lost on restart; 403 (not 404) for someone else's event.
5. Additional features implemented (quantity bookings, soft delete with ticket status, per-event ownership, concurrency-safe booking, RFC 7807/9457 Problem Details errors, documented OpenAPI with examples, concurrency demo script).
   Add a short "Design decisions and trade-offs" section (soft delete vs hard delete, 403 vs 404, one shared lock vs per-repo locks, Problem Details) and a layer diagram.
6. Future improvements and how it scales (also as `# TODO:` in the exact file):
   - Real auth (JWT/OIDC): rewrite `api/deps.py` only; services only see `user_id`.
   - Persistent DB (Postgres): new repo adapters, same ports; shared lock becomes a DB transaction; multi-instance is then safe.
   - Hot-event contention: row locks / optimistic retry; Redis counter or queue if needed.
   - Read scaling: pagination, caching, read replicas for `GET /events`.
   - Idempotency keys for `POST` bookings (a retry currently books twice).
   - Notifications and refunds on cancellation (domain events / outbox).
   - `DELETE /tickets/{id}` so users cancel their own tickets; per-user ticket limits.
   - Observability: logging and request-id middleware, metrics.
   - API evolution: `/api/v2` with separate schemas over the same services.
   - Async: async DB drivers would make port methods `async`; mechanical but touches every layer.

## Out of scope (do not build)
User registration/login, a UI, payments, a DB, Docker (not installed), a DI framework, an event bus.
