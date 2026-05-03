import uuid
from datetime import datetime
from flask import Flask, request
from flask_cors import CORS
from models import db, Email
from seeds import SEED_EMAILS

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///emails.db"
CORS(app)
db.init_app(app)

with app.app_context():
    db.create_all()


@app.route("/ping")
def ping():
    return {"message": "pong"}


@app.route("/emails", methods=["POST"])
def create_email():
    data = request.json
    email = Email(
        thread_id=data.get("thread_id") or str(uuid.uuid4()),
        sender=data["sender"],
        recipient=data["recipient"],
        subject=data["subject"],
        body=data["body"]
    )
    db.session.add(email)
    db.session.commit()
    return email.to_dict(), 201


@app.route("/emails", methods=["GET"])
def get_emails():
    query = Email.query

    thread_id = request.args.get("thread_id")
    if thread_id:
        query = query.filter_by(thread_id=thread_id)

    is_read = request.args.get("is_read")
    if is_read is not None:
        query = query.filter_by(is_read=is_read.lower() == "true")

    sender = request.args.get("sender")
    if sender:
        query = query.filter_by(sender=sender)

    recipient = request.args.get("recipient")
    if recipient:
        query = query.filter_by(recipient=recipient)

    emails = query.order_by(Email.created_at.desc()).all()
    return [email.to_dict() for email in emails]


@app.route("/emails/<int:email_id>", methods=["GET"])
def get_email(email_id):
    email = Email.query.get_or_404(email_id)
    return email.to_dict()


@app.route("/emails/<int:email_id>", methods=["PUT"])
def update_email(email_id):
    email = Email.query.get_or_404(email_id)
    data = request.json
    email.sender = data.get("sender", email.sender)
    email.recipient = data.get("recipient", email.recipient)
    email.subject = data.get("subject", email.subject)
    email.body = data.get("body", email.body)
    if "is_read" in data:
        email.is_read = data["is_read"]
    db.session.commit()
    return email.to_dict()


@app.route("/emails/<int:email_id>/read", methods=["PATCH"])
def mark_email_read(email_id):
    email = Email.query.get_or_404(email_id)
    email.is_read = True
    db.session.commit()
    return email.to_dict()


@app.route("/emails/<int:email_id>", methods=["DELETE"])
def delete_email(email_id):
    email = Email.query.get_or_404(email_id)
    db.session.delete(email)
    db.session.commit()
    return "", 204


@app.route("/threads", methods=["GET"])
def get_threads():
    threads = db.session.query(
        Email.thread_id,
        db.func.min(Email.subject).label("subject"),
        db.func.count(Email.id).label("message_count"),
        db.func.min(Email.created_at).label("first_message_at"),
        db.func.max(Email.created_at).label("last_message_at"),
        db.func.sum(db.case((Email.is_read == False, 1), else_=0)).label("unread_count")
    ).group_by(Email.thread_id).all()

    return [
        {
            "thread_id": t.thread_id,
            "subject": t.subject,
            "message_count": t.message_count,
            "first_message_at": t.first_message_at.isoformat(),
            "last_message_at": t.last_message_at.isoformat(),
            "unread_count": t.unread_count or 0
        }
        for t in threads
    ]


@app.route("/stats", methods=["GET"])
def get_stats():
    total_emails = Email.query.count()
    unread_count = Email.query.filter_by(is_read=False).count()
    thread_count = db.session.query(Email.thread_id).distinct().count()

    return {
        "total_emails": total_emails,
        "unread_count": unread_count,
        "read_count": total_emails - unread_count,
        "thread_count": thread_count
    }


@app.route("/emails", methods=["DELETE"])
def delete_emails():
    data = request.json
    Email.query.filter(Email.id.in_(data["ids"])).delete()
    db.session.commit()
    return "", 204


@app.route("/reset", methods=["POST"])
def reset_database():
    db.drop_all()
    db.create_all()
    for seed in SEED_EMAILS:
        email = Email(
            thread_id=seed.get("thread_id") or str(uuid.uuid4()),
            sender=seed["sender"],
            recipient=seed["recipient"],
            subject=seed["subject"],
            body=seed["body"],
            created_at=datetime.fromisoformat(seed["created_at"]) if seed.get("created_at") else None,
            is_read=seed.get("is_read", False)
        )
        db.session.add(email)
    db.session.commit()
    return {"message": "database reset", "emails_created": len(SEED_EMAILS)}


if __name__ == "__main__":
    app.run(debug=True)
