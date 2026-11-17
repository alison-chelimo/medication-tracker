from datetime import date, datetime, time, timedelta
from flask import Flask, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///meds.db"
app.config["SECRET_KEY"] = "dev-secret-key"
db = SQLAlchemy(app)

# The three daily time slots, and the hour each one is "due" (used for overdue alerts in Step 6)
SLOTS = ["morning", "afternoon", "evening"]
SLOT_HOURS = {"morning": 8, "afternoon": 14, "evening": 20}


# ---------- MODELS ----------

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ward = db.Column(db.String(50), nullable=False)
    bed = db.Column(db.String(10), nullable=False)
    medications = db.relationship("Medication", backref="patient",
                                  cascade="all, delete-orphan")


class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50), nullable=False)
    # Which slots this medication is scheduled for, e.g. "morning,evening"
    slots = db.Column(db.String(50), nullable=False)
    doses = db.relationship("Dose", backref="medication",
                            cascade="all, delete-orphan")

    def slot_list(self):
        return self.slots.split(",")


class Dose(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey("medication.id"), nullable=False)
    slot = db.Column(db.String(20), nullable=False)          # morning / afternoon / evening
    dose_date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending / administered
    administered_at = db.Column(db.DateTime, nullable=True)

    # The database itself blocks duplicate doses for the same medication, slot and day
    __table_args__ = (
        db.UniqueConstraint("medication_id", "slot", "dose_date",
                            name="uq_dose_per_slot_per_day"),
    )


# ---------- HELPERS ----------

def ensure_doses_for_today():
    """Create today's pending dose rows for every medication, if missing."""
    today = date.today()
    for med in Medication.query.all():
        for slot in med.slot_list():
            exists = Dose.query.filter_by(
                medication_id=med.id, slot=slot, dose_date=today
            ).first()
            if not exists:
                db.session.add(Dose(medication_id=med.id, slot=slot, dose_date=today))
    db.session.commit()


def seed_data():
    """Add demo patients and medications, only if the database is empty."""
    if Patient.query.count() > 0:
        return

    p1 = Patient(name="Grace Wanjiku", ward="Ward A", bed="1")
    p2 = Patient(name="John Otieno", ward="Ward A", bed="2")
    p3 = Patient(name="Mary Achieng", ward="Ward B", bed="1")

    p1.medications = [
        Medication(name="Paracetamol", dosage="500mg", slots="morning,afternoon,evening"),
        Medication(name="Amoxicillin", dosage="250mg", slots="morning,evening"),
    ]
    p2.medications = [
        Medication(name="Metformin", dosage="850mg", slots="morning,evening"),
        Medication(name="Amlodipine", dosage="5mg", slots="morning"),
    ]
    p3.medications = [
        Medication(name="Omeprazole", dosage="20mg", slots="morning"),
        Medication(name="Ibuprofen", dosage="400mg", slots="afternoon,evening"),
    ]

    db.session.add_all([p1, p2, p3])
    db.session.commit()

GRACE_MINUTES = 60  # how long after the due hour before a pending dose counts as overdue


def is_overdue(dose, now=None):
    """A dose is overdue if it's still pending and its slot time + grace period has passed."""
    if dose.status != "pending":
        return False
    now = now or datetime.now()
    due = datetime.combine(dose.dose_date, time(SLOT_HOURS[dose.slot], 0))
    return now > due + timedelta(minutes=GRACE_MINUTES)


# ---------- ROUTES ----------

@app.route("/")
def patient_list():
    patients = Patient.query.order_by(Patient.ward, Patient.bed).all()
    today = date.today()
    now = datetime.now()

    summary = {}
    for p in patients:
        doses = (Dose.query.join(Medication)
                 .filter(Medication.patient_id == p.id, Dose.dose_date == today)
                 .all())
        summary[p.id] = {
            "total": len(doses),
            "done": sum(1 for d in doses if d.status == "administered"),
            "overdue": sum(1 for d in doses if is_overdue(d, now)),
        }

    return render_template("patients.html", patients=patients,
                           summary=summary, today=today)

@app.route("/patients/<int:patient_id>")
def patient_detail(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    today = date.today()
    now = datetime.now()

    doses = (Dose.query.join(Medication)
             .filter(Medication.patient_id == patient.id, Dose.dose_date == today)
             .all())

    dose_map = {(d.medication_id, d.slot): d for d in doses}

    slot_pending = {slot: [] for slot in SLOTS}
    for d in doses:
        if d.status == "pending":
            slot_pending[d.slot].append(d.medication)

    # Overdue doses, used for the alert banner and the red badges
    overdue_doses = [d for d in doses if is_overdue(d, now)]
    overdue_ids = {d.id for d in overdue_doses}

    return render_template("patient_detail.html", patient=patient, today=today,
                           slots=SLOTS, dose_map=dose_map, slot_pending=slot_pending,
                           overdue_doses=overdue_doses, overdue_ids=overdue_ids)

@app.route("/doses/<int:dose_id>/administer", methods=["POST"])
def administer_dose(dose_id):
    dose = Dose.query.get_or_404(dose_id)
    patient_id = dose.medication.patient_id
    med_name = dose.medication.name
    slot = dose.slot

    # Safety: only today's doses can be administered
    if dose.dose_date != date.today():
        flash("Only today's doses can be administered.", "error")
        return redirect(url_for("patient_detail", patient_id=patient_id))

    # Duplicate guard: this UPDATE only succeeds if the dose is STILL pending.
    updated = (Dose.query
               .filter_by(id=dose_id, status="pending")
               .update({"status": "administered",
                        "administered_at": datetime.now()}))
    db.session.commit()

    if updated == 0:
        flash(f"{med_name} ({slot}) was already administered. No duplicate recorded.",
              "warning")
    else:
        flash(f"{med_name} ({slot}) marked as administered.", "success")

    return redirect(url_for("patient_detail", patient_id=patient_id))


# ---------- STARTUP ----------

with app.app_context():
    db.create_all()
    seed_data()
    ensure_doses_for_today()


if __name__ == "__main__":
    app.run(debug=True)