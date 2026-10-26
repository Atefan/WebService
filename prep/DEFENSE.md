# Defense Prep: Event Ticket Booking Service

> Written from the design in `CLAUDE.md` **before** implementation. After you build it, re-read every answer and
> fix anything that no longer matches your actual code. Answers you can't back up with the code in front of you are worthless.
> This folder (`prep/`) is for you. **Do not include it in the submission.**

---

## 1. The pitch

### 30 seconds
"It's a REST service for booking event tickets. Users can list upcoming events, book tickets and see their own tickets.
Owners can create events, cancel them and see how many tickets were booked. I built it with Python and FastAPI in four layers:
API, application, domain and infrastructure, so storage can be swapped without touching business logic. The most important rule
is that an event is never oversold, even under concurrent requests, and I prove that with a test and a demo script."

### 3 minutes (walkthrough order)
1. **What it does:** the six endpoints and the two roles (user, owner).
2. **Shape of the code:** `api -> application -> domain`, with `infrastructure` implementing the ports. Point out that the domain imports nothing.
3. **The core rule:** `Event.book()` enforces capacity; one shared lock makes check-and-update atomic.
4. **Interesting decisions:** soft delete (cancel) with ticket status, per-event ownership, Problem Details errors.
5. **Honest limits and next steps:** in-memory, no real auth, single process, and how each is fixed (README table).

---

## 2. What the system does

### Actors
- **User:** anyone with an `X-User-Id` header. Not stored; just an identifier.
- **Owner:** a user whose id is in `OWNER_IDS`. Can create events, and cancel / inspect **their own** events.

### Endpoints (`/api/v1`)
| Who | Endpoint | Result |
|---|---|---|
| user | `GET /events` | upcoming, active events with `availableTickets` |
| user | `POST /events/{id}/tickets` `{quantity}` | 201 ticket; 404 / 409 / 400 on problems |
| user | `GET /tickets` | my tickets with status `ACTIVE` or `CANCELLED` |
| owner | `POST /events` | 201 + `Location` |
| owner (own) | `DELETE /events/{id}` | 204, event and its tickets become `CANCELLED` |
| owner (own) | `GET /events/{id}/stats` | `{capacity, booked, available}` |

### Example session
1. `owner` creates "Event1" with 400 tickets, date in 2123 -> `201`, id 1.
2. `alice` lists events, sees Event1 with `availableTickets: 400`.
3. `alice` books 2 tickets -> `201`; availability is now 398.
4. `owner` checks stats -> `{capacity: 400, booked: 2, available: 398}`.
5. `owner` cancels the event -> `204`. `alice`'s `GET /tickets` now shows her ticket with `status: CANCELLED`.
6. `bob` tries to book it -> `404`. `mallory` (another owner) tries to cancel it -> `403`.

### State machines
```
Event:   ACTIVE ──cancel()──► CANCELLED   (terminal; cancel again = no-op)
Ticket:  ACTIVE ──event cancelled──► CANCELLED   (terminal)
```
Invariants: `0 <= booked <= capacity`; a CANCELLED event accepts no bookings; after cancel, no ACTIVE ticket exists for that event.

---

## 3. How it works inside

### Layers
| Layer | Responsibility | Example of what it must NOT do |
|---|---|---|
| `api` | HTTP <-> Python: routes, schemas, auth header, error mapping | Contain a capacity check |
| `application` | Use cases: order of steps, locking, clock | Import FastAPI or build JSON |
| `domain` | Entities and rules (`Event.book`, `ensure_owned_by`) | Know about HTTP, storage or locks |
| `infrastructure` | Dict-based repositories | Make business decisions |
| `main.py` | Build and connect everything | Contain logic |

Dependencies point inward only. `BookingService` depends on the `EventRepository` **Protocol**, not on the in-memory class; `main.py` injects the implementation.

### Request lifecycle (book a ticket)
header -> `Caller` -> body validated by Pydantic -> route -> `BookingService.book` -> **lock** -> get event -> date check ->
`event.book(qty)` -> save event -> add ticket -> **unlock** -> 201. Any domain error raised inside bubbles up to `api/errors.py`,
which converts it to a Problem Details response. Only that file knows status codes.

### Concurrency in one paragraph
FastAPI runs plain `def` handlers on a thread pool, so requests execute in parallel. Booking is check-then-act (read `available`, then
write `booked`), and `booked += qty` isn't atomic. Without protection two threads can both see one seat left and both book it.
One shared `RLock` serializes the compound operations `book` and `cancel`, so each runs as a unit. It's the in-process equivalent
of a DB transaction.

---

## 4. Decision log (what, why, alternative, trade-off)

| Decision | Why | Alternative | Cost of my choice |
|---|---|---|---|
| Python + FastAPI | Fastest for me; typed validation; free Swagger UI | Java/Go/C++ | Not what the reviewers write daily |
| Layered / ports and adapters | Swappable storage, testable services, easy to extend | One file with routes + dict | More files for a small task |
| In-memory repos | 2h budget; no setup for reviewers | SQLite (stdlib, persistent, transactional) | Data lost on restart; single process only |
| `X-User-Id` header | Spec says "simply pass a user id"; keeps URLs clean | Query param, path param | Spoofable (accepted by spec) |
| `OWNER_IDS` env var | Roles without storing users | Role header; user table | Static config |
| Per-event `owner_id` | Real separation between owners | Any owner manages everything | A few more lines |
| Soft delete (cancel) | Don't destroy purchases; user sees what happened | Hard delete; block delete; `?force` | Cancelled events stay in memory |
| Status on ticket | User sees cancellation directly, no join | Derive from event | Needs consistent update, hence the shared lock |
| One shared lock | Obviously correct; covers book vs cancel race | Per-repo lock; per-event lock | Serializes all writes (fine in-memory) |
| 403 for foreign event | Clear message | 404 to hide existence | Reveals the event exists (it's public anyway) |
| Problem Details (RFC 7807/9457) | Standard error format, machine-readable `code` | Custom `{error: ...}` | Slightly more fields |
| Sold-out events still listed with 0 | User sees it exists; honest | Hide them | Client filters if needed |
| Quantity per booking (default 1, max 10) | Realistic; cheap | One ticket per call | Needs a cap assumption |
| ISO-8601 UTC dates | Unambiguous (sample `04.01.2123` isn't) | Accept dd.MM.yyyy | Differs from the sample |
| Integer ids | Simple | UUID | Guessable; mitigated by ownership checks |

---

## 5. Questions and answers

### 5.1 Approach and process
**Q: Why Python/FastAPI? Your team writes Go.**
The sheet says to use a framework I'm familiar with. Python let me spend the time on design and correctness rather than tooling.
The architecture is language-neutral: the same layers map to Go packages, and the ports become Go interfaces.

**Q: Isn't four layers overkill for this size?**
The sheet explicitly rates "easy to extend". The layering costs a few small files, and it buys swappable storage, services testable without HTTP, and
a place for every future change. I avoided real over-engineering: no DI framework, no event bus, no abstract base classes.

**Q: How did you prioritize in the time?**
Core rules and tests first (booking, ownership, cancel, concurrency), then the API polish (Problem Details, OpenAPI examples), then the demo script. README was
written incrementally. Anything cut would be listed as TODO.

**Q: What would you do with another day?**
SQLite or Postgres adapters with real transactions, real auth (JWT), pagination, idempotency keys, cancel-own-ticket, notifications/refunds, Dockerfile, CI.
Each has a `# TODO:` at the exact place it plugs in.

**Q: How did you work / which tools did you use?** *(answer honestly; also check the challenge rules about tool usage beforehand)*
Be truthful and concrete, then steer to what you understand: "I planned the architecture first, then implemented in slices. I can walk through any file and
explain why it's written that way."

### 5.2 API design
**Q: Why `POST /events/{id}/tickets` and not `/bookings`?**
A ticket is the resource being created, nested under the event it belongs to. The path reads naturally, and `GET /tickets` returns the caller's tickets.
`/bookings` would also be valid; I prefer the noun the spec uses ("tickets").

**Q: Why `DELETE` for something that is really a cancellation?**
The spec says "delete events". Semantically the event is removed from the catalogue; internally it's retained as `CANCELLED` so purchases aren't destroyed. An
explicit `POST /events/{id}/cancel` is a defensible alternative and more honest about the semantics. I'd switch if cancellation needed a reason or refund policy.

**Q: Why return 204 on a second DELETE?**
DELETE is idempotent: the end state is the same, so repeating it shouldn't fail. Ownership is still checked, so strangers get 403.

**Q: Why 409 for sold out? Why not 400 or 422?**
The request is well-formed, but conflicts with the current state of the resource. That's what 409 means. 400 is for malformed input.

**Q: 403 or 404 when someone touches another owner's event?**
403: the caller is authenticated (as far as we know) but not allowed. 404 would hide existence, but events are publicly listed anyway. I documented it as an assumption.

**Q: Why 201 + `Location` on create?**
It tells the client where the new resource lives, as REST convention says. For tickets I return 201 and the ticket body.

**Q: Why `/api/v1`?**
Cheap versioning: a v2 can ship new schemas over the same services without breaking clients.

**Q: Why camelCase in JSON but snake_case in Python?**
JSON convention is camelCase and matches the sample (`availableTickets`, `eventDate`); Python convention is snake_case. A Pydantic alias generator maps between them at the boundary.

**Q: `GET /events` returns everything. What about thousands of events?**
Known gap, listed as TODO: `limit/offset` or cursor pagination, plus filters (date range, name). It'd be added in the route and `EventService.list_upcoming`; the repo port gets a paging parameter.

**Q: What if the client retries a booking after a timeout?**
It books twice. POST isn't idempotent. The fix is an `Idempotency-Key` header: store key -> result per user and return the stored result on replay. TODO in `BookingService.book`.

**Q: Why Problem Details?**
It's a standard (RFC 7807, now 9457) with a registered media type, so generic clients and tooling understand it. `code` is a stable machine-readable member, so clients don't parse messages.

**Q: How would you document the API?**
FastAPI generates OpenAPI; I added summaries, error responses and examples, so `/docs` is the interactive documentation and the README holds curl examples.

### 5.3 Domain and business rules
**Q: What exactly is "available"?**
Event is `ACTIVE` and in the future. Sold-out events are still listed with `availableTickets: 0`. Documented assumption.

**Q: What is `booked` in the stats: tickets or seats?**
Seats (sum of quantities). One ticket record can hold several seats. I'd name it clearly in the README. After cancellation `booked` is retained so the owner sees what had been sold.

**Q: What happens to tickets when an event is cancelled?**
They are kept and marked `CANCELLED`, in the same locked operation as the event status change. No refunds or notifications are implemented (TODO).

**Q: Can I book a past event? A cancelled one?**
Past: rejected (400). Cancelled: 404, same as unknown.

**Q: Can capacity be changed later?**
Not implemented. Easy to add: `Event.change_capacity(n)` with the rule `n >= booked`, a PATCH route, and an ownership check.

**Q: Where does each rule live and why?**
Rules that are always true (capacity, ownership, only ACTIVE events accept bookings) live in the **domain** so no caller can bypass them. Workflow rules (event must exist, date still in the future, quantity limits, ordering of steps) live in the **application** layer.

### 5.4 Concurrency (expect the deepest questions here)
**Q: What race are you protecting against?**
Two requests read `available = 1`, both pass the check, both increment. Result: oversold. Also book-vs-cancel: a booking sneaking in after the cancel pass leaves an ACTIVE ticket on a cancelled event.

**Q: Doesn't Python's GIL make this safe?**
No. The GIL makes single bytecode operations atomic, not sequences. `check available` then `booked += qty` is several operations and threads can interleave between them.

**Q: Why `RLock` and not `Lock`?**
Reentrant: the same thread can re-acquire it, so a service method that calls another locked method won't deadlock itself. It's defensive; a plain `Lock` also works if no nesting occurs.

**Q: Why one shared lock instead of per-repository locks?**
The invariant spans two repositories (event counter and ticket list) and two services (book, cancel). Per-repo locks can't make the whole operation atomic. One lock held around the compound operation can. The repos still protect their own internals.

**Q: Doesn't a global lock kill throughput?**
It serializes writes, but each critical section is microseconds of in-memory work. The refinement is per-event locks (a dict of locks), and eventually the database doing row-level locking.

**Q: What if I run multiple uvicorn workers or several instances?**
Then in-memory storage breaks entirely, not just the lock: each process has its own copy of the data. A shared database is required, with the invariant enforced by a transaction: `UPDATE events SET booked = booked + :q WHERE id = :id AND booked + :q <= capacity` (0 rows -> sold out), plus ticket insert in the same transaction, or `SELECT ... FOR UPDATE`.

**Q: Why `def` handlers and not `async def`?**
Handlers use blocking primitives (a threading lock). In `async def` that would block the event loop; `def` handlers run in FastAPI's thread pool. With an async DB driver I'd switch to `async def` and an async-friendly mechanism.

**Q: Any deadlock risk?**
One lock, always acquired at the top of the compound operation and released by `with`. No lock ordering problem exists with a single lock.

**Q: How do you test concurrency without flaky tests?**
Assert invariants, not timing: 50 threads, a `threading.Barrier` so they start together, capacity 10 -> exactly 10 successes, 40 `SoldOut`, `booked == 10`, 10 tickets. That holds under any interleaving. The demo script repeats it over real HTTP.

### 5.5 Architecture and scaling
**Q: What is a "port" here, concretely?**
A `typing.Protocol` in `application/ports.py` that lists the methods the services need. The in-memory classes satisfy it structurally; a SQL class would too.

**Q: Show me what changes to move to Postgres.**
New `PostgresEventRepository` / `PostgresTicketRepository`, wiring in `main.py`, and the shared lock replaced by a transaction (unit of work). Services, domain, routes and tests (except repo tests) stay.

**Q: How do you scale reads?**
Pagination first; then caching `GET /events` (short TTL or ETag), then read replicas. Reads and writes are separate code paths, so the booking path isn't affected.

**Q: A single hot event gets 10,000 simultaneous bookings?**
DB row contention becomes the bottleneck. Options: optimistic concurrency with retries, a Redis atomic decrement as a front gate, or a queue that serializes booking requests per event.

**Q: Would you split this into microservices?**
Not at this size. If events and bookings diverge in team or scale, the ports are the seams. Splitting early adds network failure modes for no gain.

**Q: How would notifications on cancellation work?**
A `Notifier` port called by `EventService.cancel` (or domain events consumed after commit via an outbox), so email/push are adapters. Currently a TODO.

**Q: How does auth evolve?**
Only `api/deps.py` changes: validate a JWT/OIDC token and build the same `Caller`. Services only know `user_id`. Per-event ownership already exists as data.

### 5.6 Security
**Q: Anyone can pass any `X-User-Id`, even the owner's.**
Correct, and accepted by the spec ("simply pass a user id"). It's documented. A real system verifies identity (JWT) and derives `user_id` from the token.

**Q: Integer ids are guessable.**
Yes. Mutating owner endpoints check ownership, and event data is public, so enumeration leaks little. UUIDs would be better for public APIs (TODO).

**Q: Input validation / abuse?**
Pydantic constrains types and ranges (capacity > 0, name non-empty and length-limited, quantity 1..10). TODO: rate limiting, max capacity, request size limits.

**Q: Do errors leak internals?**
A catch-all handler returns a generic 500 Problem Details; details go to logs, not responses.

### 5.7 Testing
**Q: What do your tests cover and why those?**
The business rules where bugs would hurt: booking math and limits, sold out, cancelled/past events, ownership, cancel cascade and idempotency, concurrency, and the API contract (status codes, Problem Details shape, auth).

**Q: How do you test time-dependent logic?**
The clock is injected as a callable, so tests pass a fixed time.

**Q: What isn't tested?**
Persistence (none exists), real multi-process behavior, and performance. I'd say so plainly.

### 5.8 Code quality
**Q: Why dataclasses in the domain but Pydantic in the API?**
Pydantic is an API-boundary concern (parsing, docs). Keeping it out of the domain means the core has no framework dependency. Cost: some field duplication between schemas and entities, which I accept for the decoupling.

**Q: Where do exceptions get handled?**
Domain exceptions carry meaning, not HTTP. They bubble untouched and are mapped once at the edge, so no layer catches and re-wraps them.

**Q: Why inject the clock and repos?**
Testability and extensibility; the composition root (`create_app`) is the only place that knows the concrete classes.

---

## 6. Live-change drills (reviewers often ask "how would you add X?")
Practise saying *where* each change goes, in this order: domain -> port -> service -> route -> test.

| Request | Domain | Port | Service | API |
|---|---|---|---|---|
| **Cancel my own ticket** | `Event.release(qty)`, `Ticket.cancel()` | `TicketRepository.get(id)` | `BookingService.cancel_ticket(user_id, id)` under the lock; 403 if not theirs; idempotent | `DELETE /tickets/{id}` |
| **Pagination** | none | `list_all(limit, offset)` | `list_upcoming(limit, offset)` | `limit`/`offset` query params, page schema |
| **Max tickets per user per event** | maybe a rule | `list_by_user_event` | sum the user's active quantity in `book` | none (400/409 via existing handlers) |
| **Change capacity** | `Event.change_capacity(n)` with `n >= booked` | none | `EventService.update` with ownership check | `PATCH /events/{id}` |
| **Persistence** | none | none | lock becomes transaction | new repos + `main.py` wiring |
| **Idempotency-Key** | none | `IdempotencyStore` port | check and store inside `book` | read the header in the route |
| **Waitlist** | `WaitlistEntry` | repo | on cancel/release, promote next | `POST /events/{id}/waitlist` |
| **Search by name/date** | none | filter args | pass through | query params |

---

## 7. Weak points they may poke (and honest answers)
| Weak point | Honest answer |
|---|---|
| Global lock | Correct and simple for one process; per-event locks or DB row locks are the next step. |
| In-memory only | A deliberate time trade-off behind a port; SQLite would be the first step. |
| No real auth | Specified by the task; isolated in `deps.py`. |
| Unbounded `GET /events` | Known; pagination is the first TODO. |
| Cancelled events accumulate | Retention/purge policy is a TODO. |
| `booked` stays after cancel | Intentional for audit; stats could include `status` (cheap improvement). |
| No refunds or notifications | Out of scope; `Notifier` port described. |
| Retry double-books | Needs `Idempotency-Key`; described. |
| Sequential integer ids | Ownership checks mitigate; UUIDs are the fix. |

Rule: **name the weakness yourself, then give the fix.** Reviewers reward awareness and punish hiding.

---

## 8. Delivery tips
- If you don't know: "I haven't done that before, but I'd approach it by..." then reason from the layers.
- Don't claim things the code doesn't do. If a feature is a TODO, say TODO.
- Know the files in this order so you can navigate live: `main.py` -> `domain/models.py` -> `application/*_service.py` -> `infrastructure/in_memory_repos.py` -> `api/routes.py`, `deps.py`, `errors.py` -> tests.
- Have the demo ready: start the server, open `/docs`, run the concurrency script.
- Memorize the status codes: 201 created, 204 no content, 400 invalid, 401 no identity, 403 not allowed, 404 not found, 409 conflict.

### Final self-check before submitting
- [ ] I can explain every file and why it exists.
- [ ] I can explain the race condition and the lock without notes.
- [ ] README: run steps, example requests, assumptions, extras, TODOs, decisions.
- [ ] Fresh venv -> `pip install -r requirements.txt` -> server starts -> tests pass.
- [ ] `prep/` and `.venv/` are not in the submission.
