# Medication Management System

A Flask web app that helps nursing staff track patients' medications and
their morning / afternoon / evening doses.

## Run it

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Demo patients are seeded on first run.

## How it maps to the acceptance criteria

| Criterion | Where it is handled |
|-----------|---------------------|
| Nurse can view all assigned patients | Patient list page (`/`) |
| Each patient shows one or more medications | Patient detail page |
| Three possible doses per medication | `Medication.slots` (morning, afternoon, evening) |
| Pending vs. completed per slot | `Dose.status`, shown as badges in the schedule grid |
| Mark a dose as "administered" | `POST /doses/<id>/administer` |
| Prevent duplicate or missed entries | See below |

## Data model

- **Patient**: name, ward, bed
- **Medication**: belongs to a patient; name, dosage, which slots it uses
- **Dose**: one scheduled administration of a medication on one day;
  status (`pending` / `administered`) and `administered_at` timestamp

## Preventing duplicates and missed doses

- A unique constraint on `(medication_id, slot, dose_date)` stops duplicate
  dose rows in the database.
- Administering uses a single `UPDATE ... WHERE status = 'pending'`, so a dose
  cannot be recorded twice, even with two nurses clicking at once.
- A pending dose is flagged **overdue** once its slot time plus a 60-minute
  grace period has passed (08:00, 14:00, 20:00). This is calculated on each
  page load.

## Design decisions

- Server-rendered pages (Flask + Jinja) to keep the app simple.
- Changes use POST forms followed by a redirect.
- SQLite for zero-setup storage.

## Limitations and next steps

- No login or nurse identity (a real system needs authentication and an
  audit log of who administered each dose).
- Overdue is derived, not stored. A scheduled job could mark doses `missed`
  and send notifications.
- Only today's doses can be administered.
- Slot times and grace period are constants in `app.py`.
- Secrte key is hard-coded for the demo and would come from an environment variable in production.

