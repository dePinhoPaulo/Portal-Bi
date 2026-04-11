from flask import request, jsonify, render_template, redirect, url_for, make_response
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity,
    set_access_cookies, unset_jwt_cookies
)
from auth import hash_password, check_password
from powerbi import get_embed_token
from datetime import datetime

def init_routes(app, db, User, Report, Permission, AccessLog):

    @app.route("/")
    def index():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html")
        data = request.form
        user = User.query.filter_by(email=data["email"], active=True).first()
        if not user or not check_password(data["password"], user.password_hash):
            return render_template("login.html", error="Email ou senha incorretos.")
        token = create_access_token(identity=str(user.id))
        response = make_response(redirect(url_for("dashboard")))
        set_access_cookies(response, token)
        return response

    @app.route("/logout")
    def logout():
        response = make_response(redirect(url_for("login")))
        unset_jwt_cookies(response)
        return response

    @app.route("/dashboard")
    @jwt_required()
    def dashboard():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if user.is_admin:
            reports = Report.query.filter_by(active=True).all()
        else:
            perms = Permission.query.filter_by(user_id=user_id).all()
            report_ids = [p.report_id for p in perms]
            reports = Report.query.filter(
                Report.id.in_(report_ids), Report.active == True
            ).all()
        return render_template("dashboard.html", user=user, reports=reports)

    @app.route("/report/<int:report_id>")
    @jwt_required()
    def view_report(report_id):
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        report = Report.query.get_or_404(report_id)
        if not user.is_admin:
            perm = Permission.query.filter_by(
                user_id=user_id, report_id=report_id
            ).first()
            if not perm:
                return redirect(url_for("dashboard"))
        log = AccessLog(
            user_id=user_id,
            report_id=report_id,
            ip_address=request.remote_addr,
            accessed_at=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()
        embed_data = get_embed_token(
            report.workspace_id,
            report.report_id,
            user=user,
            has_rls=report.has_rls
        )
        return render_template("report.html", user=user, report=report, embed=embed_data)

    @app.route("/admin/users")
    @jwt_required()
    def admin_users():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user.is_admin:
            return redirect(url_for("dashboard"))
        users = User.query.all()
        return render_template("admin_users.html", user=user, users=users)

    @app.route("/admin/users/create", methods=["POST"])
    @jwt_required()
    def admin_create_user():
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        data = request.form
        new_user = User(
            name=data["name"],
            email=data["email"],
            password_hash=hash_password(data["password"]),
            is_admin=data.get("is_admin") == "on",
            role=data.get("role", "user"),
            empresa_revenda=data.get("empresa_revenda") or None
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("admin_users"))

    @app.route("/admin/permissions")
    @jwt_required()
    def admin_permissions():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user.is_admin:
            return redirect(url_for("dashboard"))
        users = User.query.filter_by(is_admin=False, active=True).all()
        reports = Report.query.filter_by(active=True).all()
        permissions = Permission.query.all()
        return render_template(
            "admin_permissions.html",
            user=user, users=users,
            reports=reports, permissions=permissions
        )

    @app.route("/admin/permissions/toggle", methods=["POST"])
    @jwt_required()
    def toggle_permission():
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        data = request.json
        perm = Permission.query.filter_by(
            user_id=data["user_id"], report_id=data["report_id"]
        ).first()
        if perm:
            db.session.delete(perm)
            db.session.commit()
            return jsonify({"status": "removed"})
        new_perm = Permission(user_id=data["user_id"], report_id=data["report_id"])
        db.session.add(new_perm)
        db.session.commit()
        return jsonify({"status": "added"})

    @app.route("/admin/logs")
    @jwt_required()
    def admin_logs():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user.is_admin:
            return redirect(url_for("dashboard"))
        logs = db.session.query(AccessLog, User, Report)\
            .join(User, AccessLog.user_id == User.id)\
            .join(Report, AccessLog.report_id == Report.id)\
            .order_by(AccessLog.accessed_at.desc()).limit(200).all()
        return render_template("admin_logs.html", user=user, logs=logs)

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        if User.query.count() > 0:
            return redirect(url_for("login"))
        if request.method == "POST":
            data = request.form
            admin = User(
                name=data["name"],
                email=data["email"],
                password_hash=hash_password(data["password"]),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            return redirect(url_for("login"))
        return render_template("setup.html")
    
    @app.route("/admin/reports")
    @jwt_required()
    def admin_reports():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user.is_admin:
            return redirect(url_for("dashboard"))
        reports = Report.query.order_by(Report.created_at.desc()).all()
        return render_template("admin_reports.html", user=user, reports=reports)

    @app.route("/admin/reports/create", methods=["POST"])
    @jwt_required()
    def admin_create_report():
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        data = request.form
        new_report = Report(
            name=data["name"],
            description=data.get("description", ""),
            report_id=data["report_id"],
            workspace_id=data["workspace_id"],
            has_rls=data.get("has_rls") == "on",
            active=True
        )
        db.session.add(new_report)
        db.session.commit()
        return redirect(url_for("admin_reports"))

    @app.route("/admin/reports/toggle/<int:report_id>", methods=["POST"])
    @jwt_required()
    def admin_toggle_report(report_id):
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        report = Report.query.get_or_404(report_id)
        report.active = not report.active
        db.session.commit()
        return redirect(url_for("admin_reports"))

    @app.route("/admin/reports/delete/<int:report_id>", methods=["POST"])
    @jwt_required()
    def admin_delete_report(report_id):
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        report = Report.query.get_or_404(report_id)
        Permission.query.filter_by(report_id=report_id).delete()
        db.session.delete(report)
        db.session.commit()
        return redirect(url_for("admin_reports"))

    @app.route("/admin/reports/edit/<int:report_id>", methods=["POST"])
    @jwt_required()
    def admin_edit_report(report_id):
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        report = Report.query.get_or_404(report_id)
        data = request.form
        report.name         = data["name"]
        report.description  = data.get("description", "")
        report.report_id    = data["report_id"]
        report.workspace_id = data["workspace_id"]
        report.has_rls      = data.get("has_rls") == "on"
        db.session.commit()
        return redirect(url_for("admin_reports"))