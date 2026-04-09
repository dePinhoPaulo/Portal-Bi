from datetime import datetime

def init_models(db):

    class User(db.Model):
        __tablename__ = "users"
        id            = db.Column(db.Integer, primary_key=True)
        name          = db.Column(db.String(100), nullable=False)
        email         = db.Column(db.String(150), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        is_admin      = db.Column(db.Boolean, default=False)
        active        = db.Column(db.Boolean, default=True)
        created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    class Report(db.Model):
        __tablename__ = "reports"
        id           = db.Column(db.Integer, primary_key=True)
        name         = db.Column(db.String(150), nullable=False)
        description  = db.Column(db.String(300))
        report_id    = db.Column(db.String(100), nullable=False)
        workspace_id = db.Column(db.String(100), nullable=False)
        active       = db.Column(db.Boolean, default=True)
        created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    class Permission(db.Model):
        __tablename__ = "permissions"
        id         = db.Column(db.Integer, primary_key=True)
        user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
        report_id  = db.Column(db.Integer, db.ForeignKey("reports.id"), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class AccessLog(db.Model):
        __tablename__ = "access_logs"
        id          = db.Column(db.Integer, primary_key=True)
        user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
        report_id   = db.Column(db.Integer, db.ForeignKey("reports.id"), nullable=False)
        ip_address  = db.Column(db.String(50))
        accessed_at = db.Column(db.DateTime, default=datetime.utcnow)

    return User, Report, Permission, AccessLog

def create_tables(db):
    db.create_all()
    print("Tabelas criadas com sucesso!")