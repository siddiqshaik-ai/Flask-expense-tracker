import csv
import io
from flask import Response
from datetime import datetime,timezone
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = "supersecretkey"  
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(60), nullable=False, default="General")
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    notes = db.Column(db.Text)

@app.route("/")
def index():
    selected_category = request.args.get("category", "All")
    selected_month = request.args.get("month", "")

    query = Expense.query

    if selected_category != "All":
        query = query.filter(Expense.category == selected_category)

    if selected_month:
        year, month = map(int, selected_month.split("-"))
        query = query.filter(
            func.extract("year", Expense.date) == year,
            func.extract("month", Expense.date) == month
        )

    expenses = query.order_by(Expense.date.desc()).all()
    total = sum(float(e.amount) for e in expenses)

    category_rows = (
        query.with_entities(Expense.category, func.sum(Expense.amount))
        .group_by(Expense.category)
        .all()
    )
    cat_labels = [r[0] for r in category_rows]
    cat_totals = [float(r[1] or 0) for r in category_rows]
    
    top_category = None
    top_amount = 0
    if category_rows:
        top_category, top_amount = max(
            category_rows,
            key=lambda r: float(r[1] or 0)
        )

    monthly = defaultdict(float)
    for e in expenses:
        key = e.date.strftime("%Y-%m")
        monthly[key] += float(e.amount)

    month_labels = list(monthly.keys())
    month_totals = list(monthly.values())
    categories = [
        row[0]
        for row in db.session.query(Expense.category)
        .distinct()
        .order_by(Expense.category)
        .all()
    ]
    categories.insert(0, "All")

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        categories=categories,
        selected_category=selected_category,
        selected_month=selected_month,
        month_labels=month_labels,
        month_totals=month_totals,
        cat_labels=cat_labels,
        cat_totals=cat_totals,
        top_category=top_category,
        top_amount=top_amount,
    )
@app.route("/export")
def export_csv():
    # Read filters (same as index)
    selected_category = request.args.get("category", "All")
    selected_month = request.args.get("month", "")

    # Build query
    query = Expense.query

    if selected_category and selected_category != "All":
        query = query.filter(Expense.category == selected_category)

    if selected_month:
        year, month = map(int, selected_month.split("-"))
        query = query.filter(
            db.extract("year", Expense.date) == year,
            db.extract("month", Expense.date) == month
        )

    expenses = query.order_by(Expense.date.desc()).all()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Date", "Title", "Category", "Amount", "Notes"])

    # Rows
    for e in expenses:
        writer.writerow([
            e.date.strftime("%Y-%m-%d"),
            e.title,
            e.category,
            f"{float(e.amount):.2f}",
            e.notes or ""
        ])

    csv_data = output.getvalue()
    output.close()

    # Download response
    filename = "expenses.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        expense = Expense(
            title=request.form["title"],
            amount=float(request.form["amount"]),
            category=request.form.get("category") or "General",
            date=datetime.strptime(request.form["date"], "%Y-%m-%d"),
            notes=request.form.get("notes")
        )
        db.session.add(expense)
        db.session.commit()
        flash("Expense added successfully ✅", "success")
        return redirect(url_for("index"))
    return render_template("add_edit.html", expense=None)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    expense = Expense.query.get_or_404(id)
    if request.method == "POST":
        expense.title = request.form["title"]
        expense.amount = float(request.form["amount"])
        expense.category = request.form.get("category") or "General"
        expense.date = datetime.strptime(request.form["date"], "%Y-%m-%d")
        expense.notes = request.form.get("notes")
        db.session.commit()
        flash("Expense updated successfully ✏️", "success")
        return redirect(url_for("index"))
    return render_template("add_edit.html", expense=expense)

@app.route("/delete/<int:id>")
def delete(id):
    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted 🗑️", "danger")
    return redirect(url_for("index"))
@app.route("/test")
def test():
    return "Flask is working ✅"
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        app.run(debug=True, use_reloader=False)





