# DarkStore Ops Tracker

A Flask operations dashboard for a quick-commerce dark store: the small
warehouse that picks, packs and dispatches grocery orders in minutes.
It tracks the order pipeline against per-stage SLA targets, watches
inventory for stock-outs, runs a rider dispatch board, tracks team
commitments to completion, logs process bottlenecks with measured
results, and exports the whole day as an Excel report.

Built to demonstrate the day-to-day work of a **Project Management /
Operations internship** (order tracking, coordination across teams,
process improvement, commitment follow-up, Excel reporting) — the kind
of role where the job is keeping a fast-moving operation on track, not
writing production code.

## How each feature maps to PM / ops work

| Feature | What it does | The PM/ops skill it shows |
|---|---|---|
| Order pipeline tracker | Orders move placed → picked → packed → dispatched → delivered, with timestamps, SLA targets per stage (pick 8 min, pack 5 min, dispatch 5 min, deliver 25 min, 45-min promise) and breach flags, including orders stuck mid-pipeline | Operational strategy & execution: monitoring daily ops, spotting what is late |
| Inventory / stock-out tracker | 18 SKUs with stock levels, reorder points, stock-out and low-stock alerts | Daily ops monitoring: knowing what will block fulfilment before it does |
| Rider dispatch board | Riders on shift, availability, deliveries completed today | Team enablement: coordinating the people who execute the plan |
| Task & commitment tracker | Tasks with owners, teams, due times and status; anything past due and still open is flagged overdue for follow-up | Communication & commitment tracking: following up until commitments hit 100% completion |
| Daily ops summary dashboard | Orders, on-time %, average pick/pack/dispatch/delivery times, stock-outs, open and overdue commitments | Data-backed operations: reading the day in numbers, not anecdotes |
| Excel daily report (.xlsx) | One-click export of the full day: Summary, Orders, Inventory, Riders, Tasks and Bottlenecks sheets | MS-Excel reporting: the report the area manager actually opens |
| Bottleneck log | Record an inefficiency, the action taken, and the measured before/after result | Process optimisation & problem-solving: structured fixes with evidence |

## Quick start

```bash
./run.sh        # creates a venv, installs deps, seeds demo data, starts the app
```

Or manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m darkstore.cli seed    # load one demo day of data
.venv/bin/python -m darkstore.cli demo    # print the daily summary
.venv/bin/python -m darkstore.cli serve   # web dashboard at http://127.0.0.1:5000
```

Pages: `/` dashboard, `/orders`, `/inventory`, `/riders`, `/tasks`,
`/bottlenecks`, `/export` (downloads the daily `.xlsx` report),
`/api/summary` (JSON).

## Demo walkthrough

The seed loads one demo day for a fictional store: 24 live orders
(21 delivered, 3 still in the pipeline, 1 cancelled), 4 riders,
18 inventory items, 9 team tasks and 3 logged bottlenecks.

1. Open `/` — the day at a glance: 95.2% on-time delivery, average
   pick 6.7 min, 2 stock-outs, 2 overdue commitments.
2. Open `/orders` — find the order flagged for a 14-minute pick
   (SLA: 8 min) and the order placed 35 minutes ago that still has
   not been picked. Use **Advance** to move an order to its next stage.
3. Open `/inventory` — onion and eggs are stocked out, tomato,
   butter and biscuits are low.
4. Open `/tasks` — two commitments are overdue; use **Mark done**
   when an owner confirms completion and watch the completion %
   move.
5. Open `/bottlenecks` — one resolved issue with a measured result
   (pick time 11.5 → 6.8 min after splitting the dairy rack into
   two pick zones) and two open ones.
6. Click **Export daily report (.xlsx)** — the full day as a
   six-sheet Excel workbook.

## Tests

```bash
python -m pytest tests/ -v
```

12 tests, all passing: SLA breach detection (completed and waiting),
on-time vs late delivery, cancelled orders never breaching, pipeline
stage transitions in order, task overdue logic, dashboard aggregates
on the seeded day, stock-out vs low-stock split, Excel export contents
(all six sheets, row counts, on-time % in the summary), and web
smoke tests (dashboard renders, export returns a valid .xlsx).

## Tech stack

Python 3, Flask, SQLAlchemy (SQLite), Pandas (aggregates), openpyxl
(Excel export). No JavaScript framework, no external services.

## What it does not do

- It is not connected to any real store, Blinkit system or live data.
  Every order, rider, product and task is invented demo data, and the
  app says so on every page.
- It does not predict demand, optimise routes or auto-assign riders;
  assignment and decisions stay with the human running the shift.
- It is a single-store demo: no multi-store roll-up, no auth, no
  user accounts.
