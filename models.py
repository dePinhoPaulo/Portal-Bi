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
        role          = db.Column(db.String(20), default='user')
        empresa_revenda = db.Column(db.String(50))
        created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    class Report(db.Model):
        __tablename__ = "reports"
        id           = db.Column(db.Integer, primary_key=True)
        name         = db.Column(db.String(150), nullable=False)
        description  = db.Column(db.String(300))
        report_id    = db.Column(db.String(100), nullable=False)
        workspace_id = db.Column(db.String(100), nullable=False)
        has_rls      = db.Column(db.Boolean, default=False)
        active       = db.Column(db.Boolean, default=True)
        created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    class Group(db.Model):
        __tablename__ = "groups"
        id          = db.Column(db.Integer, primary_key=True)
        name        = db.Column(db.String(150), nullable=False)
        description = db.Column(db.String(300))
        active      = db.Column(db.Boolean, default=True)
        created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    class ReportGroup(db.Model):
        __tablename__ = "report_groups"
        id        = db.Column(db.Integer, primary_key=True)
        report_id = db.Column(db.Integer, db.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
        group_id  = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
        __table_args__ = (db.UniqueConstraint("report_id", "group_id"),)

    class Permission(db.Model):
        __tablename__ = "permissions"
        id        = db.Column(db.Integer, primary_key=True)
        user_id   = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
        report_id = db.Column(db.Integer, db.ForeignKey("reports.id", ondelete="CASCADE"), nullable=True)
        group_id  = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class AccessLog(db.Model):
        __tablename__ = "access_logs"
        id          = db.Column(db.Integer, primary_key=True)
        user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
        report_id   = db.Column(db.Integer, db.ForeignKey("reports.id"), nullable=False)
        ip_address  = db.Column(db.String(50))
        accessed_at = db.Column(db.DateTime, default=datetime.utcnow)

    return User, Report, Group, ReportGroup, Permission, AccessLog

def create_tables(db):
    db.create_all()
    print("Tabelas criadas com sucesso!")