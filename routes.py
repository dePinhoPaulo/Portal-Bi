from flask import request, jsonify, render_template, redirect, url_for, make_response
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity,
    set_access_cookies, unset_jwt_cookies
)
from auth import hash_password, check_password
from powerbi import get_embed_token
from datetime import datetime
from sqlalchemy import or_

def init_routes(app, db, User, Report, ReportRLS, Group, ReportGroup, Permission, AccessLog):

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
            groups  = Group.query.filter_by(active=True).order_by(Group.name).all()
            # Relatórios sem grupo
            grouped_ids = [rg.report_id for rg in ReportGroup.query.all()]
            loose = Report.query.filter_by(active=True).filter(
                ~Report.id.in_(grouped_ids) if grouped_ids else True
            ).all()
        else:
            # Grupos liberados para o usuário
            group_perms = Permission.query.filter_by(user_id=user_id, report_id=None).all()
            group_ids   = [p.group_id for p in group_perms]
            groups      = Group.query.filter(
                Group.id.in_(group_ids), Group.active == True
            ).order_by(Group.name).all()

            # Relatórios avulsos liberados
            report_perms = Permission.query.filter_by(user_id=user_id, group_id=None).all()
            report_ids   = [p.report_id for p in report_perms]

            # Remove relatórios que já aparecem em grupos liberados
            grouped_report_ids = [
                rg.report_id for rg in ReportGroup.query.filter(
                    ReportGroup.group_id.in_(group_ids)
                ).all()
            ] if group_ids else []

            loose_ids = [rid for rid in report_ids if rid not in grouped_report_ids]
            loose = Report.query.filter(
                Report.id.in_(loose_ids), Report.active == True
            ).all() if loose_ids else []

        # Monta estrutura de grupos com seus relatórios
        groups_data = []
        for g in groups:
            rg_ids = [rg.report_id for rg in ReportGroup.query.filter_by(group_id=g.id).all()]
            reports = Report.query.filter(
                Report.id.in_(rg_ids), Report.active == True
            ).all() if rg_ids else []
            if reports:
                groups_data.append({"group": g, "reports": reports})

        return render_template("dashboard.html",
            user=user,
            groups_data=groups_data,
            loose_reports=loose
        )

    @app.route("/report/<int:report_id>")
    @jwt_required()
    def view_report(report_id):
        user_id = int(get_jwt_identity())
        user    = User.query.get(user_id)
        report  = Report.query.get_or_404(report_id)

        if not user.is_admin:
            direct    = Permission.query.filter_by(
                user_id=user_id, report_id=report_id, group_id=None
            ).first()
            rg_entries = ReportGroup.query.filter_by(report_id=report_id).all()
            group_ids  = [rg.group_id for rg in rg_entries]
            via_group  = Permission.query.filter(
                Permission.user_id == user_id,
                Permission.group_id.in_(group_ids),
                Permission.report_id == None
            ).first() if group_ids else None
            if not direct and not via_group:
                return redirect(url_for("dashboard"))

        log = AccessLog(
            user_id=user_id, report_id=report_id,
            ip_address=request.remote_addr,
            accessed_at=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()

        rls_config = ReportRLS.query.filter_by(report_id=report_id).first()
        embed_data = get_embed_token(
            report.workspace_id, report.report_id,
            user=user, has_rls=report.has_rls, rls_config=rls_config
        )
        return render_template("report.html", user=user, report=report, embed=embed_data)
    
    # ── Admin Users ─────────────────────────────────────────────

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
            empresa_revenda=data["empresa_revenda"] or None
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("admin_users"))

    # ── Admin Reports ────────────────────────────────────────────

    @app.route("/admin/reports")
    @jwt_required()
    def admin_reports():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user.is_admin:
            return redirect(url_for("dashboard"))
        reports = Report.query.order_by(Report.created_at.desc()).all()
        # Injeta o rls em cada relatório para o template acessar como r.rls
        for r in reports:
            r.rls = ReportRLS.query.filter_by(report_id=r.id).first()
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
        ReportGroup.query.filter_by(report_id=report_id).delete()
        db.session.delete(report)
        db.session.commit()
        return redirect(url_for("admin_reports"))

    # ── Admin Groups ─────────────────────────────────────────────

    @app.route("/admin/groups")
    @jwt_required()
    def admin_groups():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user.is_admin:
            return redirect(url_for("dashboard"))
        groups  = Group.query.order_by(Group.created_at.desc()).all()
        reports = Report.query.filter_by(active=True).order_by(Report.name).all()
        # Para cada grupo, quais relatórios ele tem
        group_report_ids = {}
        for g in groups:
            group_report_ids[g.id] = [
                rg.report_id for rg in ReportGroup.query.filter_by(group_id=g.id).all()
            ]
        return render_template("admin_groups.html",
            user=user, groups=groups,
            reports=reports, group_report_ids=group_report_ids
        )

    @app.route("/admin/groups/create", methods=["POST"])
    @jwt_required()
    def admin_create_group():
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        data = request.form
        group = Group(
            name=data["name"],
            description=data.get("description", ""),
            active=True
        )
        db.session.add(group)
        db.session.flush()
        for rid in request.form.getlist("report_ids"):
            db.session.add(ReportGroup(group_id=group.id, report_id=int(rid)))
        db.session.commit()
        return redirect(url_for("admin_groups"))

    @app.route("/admin/groups/edit/<int:group_id>", methods=["POST"])
    @jwt_required()
    def admin_edit_group(group_id):
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        group = Group.query.get_or_404(group_id)
        data  = request.form
        group.name        = data["name"]
        group.description = data.get("description", "")
        ReportGroup.query.filter_by(group_id=group_id).delete()
        for rid in request.form.getlist("report_ids"):
            db.session.add(ReportGroup(group_id=group_id, report_id=int(rid)))
        db.session.commit()
        return redirect(url_for("admin_groups"))

    @app.route("/admin/groups/toggle/<int:group_id>", methods=["POST"])
    @jwt_required()
    def admin_toggle_group(group_id):
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        group = Group.query.get_or_404(group_id)
        group.active = not group.active
        db.session.commit()
        return redirect(url_for("admin_groups"))

    @app.route("/admin/groups/delete/<int:group_id>", methods=["POST"])
    @jwt_required()
    def admin_delete_group(group_id):
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        ReportGroup.query.filter_by(group_id=group_id).delete()
        Permission.query.filter_by(group_id=group_id).delete()
        Group.query.filter_by(id=group_id).delete()
        db.session.commit()
        return redirect(url_for("admin_groups"))

    # ── Admin Permissions ────────────────────────────────────────

    @app.route("/admin/permissions")
    @jwt_required()
    def admin_permissions():
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user.is_admin:
            return redirect(url_for("dashboard"))
        users   = User.query.filter_by(is_admin=False, active=True).all()
        groups  = Group.query.filter_by(active=True).order_by(Group.name).all()
        reports = Report.query.filter_by(active=True).order_by(Report.name).all()
        perms   = Permission.query.all()
        return render_template("admin_permissions.html",
            user=user, users=users,
            groups=groups, reports=reports, perms=perms
        )

    @app.route("/admin/permissions/toggle", methods=["POST"])
    @jwt_required()
    def toggle_permission():
        user_id = int(get_jwt_identity())
        admin = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403
        data      = request.json
        target_uid = data["user_id"]
        group_id  = data.get("group_id")
        report_id = data.get("report_id")

        if group_id:
            perm = Permission.query.filter_by(
                user_id=target_uid, group_id=group_id, report_id=None
            ).first()
        else:
            perm = Permission.query.filter_by(
                user_id=target_uid, report_id=report_id, group_id=None
            ).first()

        if perm:
            db.session.delete(perm)
            db.session.commit()
            return jsonify({"status": "removed"})

        new_perm = Permission(
            user_id=target_uid,
            group_id=group_id if group_id else None,
            report_id=report_id if report_id else None
        )
        db.session.add(new_perm)
        db.session.commit()
        return jsonify({"status": "added"})

    # ── Admin Logs ───────────────────────────────────────────────

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

    # ── Setup ────────────────────────────────────────────────────

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
    
    # ── Admin RLS ────────────────────────────────────────────────

    @app.route("/admin/reports/<int:report_id>/rls", methods=["POST"])
    @jwt_required()
    def admin_save_rls(report_id):
        user_id = int(get_jwt_identity())
        admin   = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403

        data   = request.form
        report = Report.query.get_or_404(report_id)

        # Ativa RLS no relatório
        report.has_rls = True
        db.session.flush()

        # Cria ou atualiza configuração RLS
        rls = ReportRLS.query.filter_by(report_id=report_id).first()
        if rls:
            rls.role_name     = data["role_name"]
            rls.filter_source = data["filter_source"]
            rls.description   = data.get("description", "")
        else:
            rls = ReportRLS(
                report_id     = report_id,
                role_name     = data["role_name"],
                filter_source = data["filter_source"],
                description   = data.get("description", "")
            )
            db.session.add(rls)

        db.session.commit()
        return redirect(url_for("admin_reports"))

    @app.route("/admin/reports/<int:report_id>/rls/delete", methods=["POST"])
    @jwt_required()
    def admin_delete_rls(report_id):
        user_id = int(get_jwt_identity())
        admin   = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403

        report = Report.query.get_or_404(report_id)
        report.has_rls = False
        ReportRLS.query.filter_by(report_id=report_id).delete()
        db.session.commit()
        return redirect(url_for("admin_reports"))

    @app.route("/admin/users/edit/<int:target_id>", methods=["POST"])
    @jwt_required()
    def admin_edit_user(target_id):
        user_id = int(get_jwt_identity())
        admin   = User.query.get(user_id)
        if not admin.is_admin:
            return jsonify({"error": "Sem permissão"}), 403

        data = request.form
        u    = User.query.get_or_404(target_id)
        u.name            = data["name"]
        u.email           = data["email"]
        u.role            = data.get("role", "user")
        u.empresa_revenda = data.get("empresa_revenda") or None
        u.departamento    = data.get("departamento") or None
        u.is_admin        = data.get("is_admin") == "on"
        u.active          = data.get("active") == "on"
        if data.get("password"):
            from auth import hash_password
            u.password_hash = hash_password(data["password"])
        db.session.commit()
        return redirect(url_for("admin_users"))