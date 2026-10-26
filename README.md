# Event Ticket Booking Service

RESTful service where users book tickets for events and owners maintain events.
Python 3.12, FastAPI, in-memory storage.

> Skeleton only: business logic is not implemented yet.

## Architecture
TODO: layer diagram (api -> application -> domain; infrastructure implements application ports) and why.

## How to run
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Swagger UI: http://127.0.0.1:8000/docs

Environment variables:
- `OWNER_IDS`: comma-separated user ids that are event owners (default `owner`)
- `MAX_TICKETS_PER_BOOKING`: default `10`

Tests: `pytest`

## Example requests
TODO: curl examples (also in `requests.http`).

## Assumptions
TODO: fill in as decisions are made (see CLAUDE.md for the list).

## Additional features
TODO

## Design decisions and trade-offs
TODO

## Future improvements
TODO
