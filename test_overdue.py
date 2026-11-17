from datetime import date, datetime
from app import app, Dose, is_overdue

with app.app_context():
    d = Dose(slot="morning", dose_date=date(2026, 11, 17), status="pending")

    # 08:30 is inside the 60-minute grace period -> not overdue
    assert not is_overdue(d, datetime(2026, 11, 17, 8, 30))
    # 09:30 is past 08:00 + 60 min -> overdue
    assert is_overdue(d, datetime(2026, 11, 17, 9, 30))

    # An administered dose is never overdue
    d.status = "administered"
    assert not is_overdue(d, datetime(2026, 11, 17, 23, 0))

    print("All overdue tests passed")