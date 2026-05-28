from flask import Blueprint, request, render_template, redirect, url_for, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, cast
from sqlalchemy.types import Date
from datetime import datetime, timedelta, timezone
from .helpers import check_module_access
import csv, io

BRASILIA      = timezone(timedelta(hours=-3))
admin_logs_bp = Blueprint("admin_logs", __name__)

@admin_logs_bp.route("/admin/logs")
@jwt_required()
def admin_logs():
    ctx       = admin_logs_bp.ctx
    db        = ctx["db"]
    User      = ctx["User"]
    Report    = ctx["Report"]
    Role      = ctx["Role"]
    AccessLog = ctx["AccessLog"]
    user_id   = int(get_jwt_identity())
    user      = db.session.get(User, user_id)
    if not check_module_access(ctx, user, "logs"):
        return redirect(url_for("dashboard.dashboard"))

    f_q         = request.args.get("q",          "").strip()
    f_user      = request.args.get("user_id",    "").strip()
    f_role      = request.args.get("role",        "").strip()
    f_report    = request.args.get("report_id",  "").strip()
    f_date_from = request.args.get("date_from",   "").strip()
    f_date_to   = request.args.get("date_to",     "").strip()

    query = db.session.query(AccessLog, User, Report)\
        .join(User,   AccessLog.user_id   == User.id)\
        .join(Report, AccessLog.report_id == Report.id)

    if f_user:   query = query.filter(AccessLog.user_id == int(f_user))
    if f_role:   query = query.filter(User.role == f_role)
    if f_report: query = query.filter(AccessLog.report_id == int(f_report))
    if f_q:
        query = query.filter(db.or_(
            User.name.ilike(f"%{f_q}%"), Report.name.ilike(f"%{f_q}%")
        ))
    if f_date_from:
        try:
            query = query.filter(
                AccessLog.accessed_at >= datetime.strptime(f_date_from, "%Y-%m-%d")
            )
        except Exception:
            pass
    if f_date_to:
        try:
            query = query.filter(
                AccessLog.accessed_at < datetime.strptime(f_date_to, "%Y-%m-%d") + timedelta(days=1)
            )
        except Exception:
            pass

    page     = request.args.get("page", 1, type=int)
    per_page = 50
    paginate = query.order_by(AccessLog.accessed_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    logs = paginate.items

    all_users   = User.query.filter_by(active=True).order_by(User.name).all()
    all_reports = Report.query.filter_by(active=True).order_by(Report.name).all()
    all_roles   = Role.query.filter_by(active=True).order_by(Role.label).all()

    return render_template("admin_logs.html",
        user=user, logs=logs, paginate=paginate,
        all_users=all_users, all_reports=all_reports, all_roles=all_roles,
        f_q=f_q, f_user=f_user, f_role=f_role, f_report=f_report,
        f_date_from=f_date_from, f_date_to=f_date_to)


@admin_logs_bp.route("/admin/logs/export")
@jwt_required()
def export_logs_csv():
    ctx       = admin_logs_bp.ctx
    db        = ctx["db"]
    User      = ctx["User"]
    Report    = ctx["Report"]
    AccessLog = ctx["AccessLog"]
    user_id   = int(get_jwt_identity())
    user      = db.session.get(User, user_id)
    if not check_module_access(ctx, user, "logs"):
        return redirect(url_for("dashboard.dashboard"))

    f_q         = request.args.get("q",          "").strip()
    f_user      = request.args.get("user_id",    "").strip()
    f_role      = request.args.get("role",        "").strip()
    f_report    = request.args.get("report_id",  "").strip()
    f_date_from = request.args.get("date_from",   "").strip()
    f_date_to   = request.args.get("date_to",     "").strip()

    query = db.session.query(AccessLog, User, Report)\
        .join(User,   AccessLog.user_id   == User.id)\
        .join(Report, AccessLog.report_id == Report.id)

    if f_user:   query = query.filter(AccessLog.user_id == int(f_user))
    if f_role:   query = query.filter(User.role == f_role)
    if f_report: query = query.filter(AccessLog.report_id == int(f_report))
    if f_q:
        query = query.filter(db.or_(
            User.name.ilike(f"%{f_q}%"), Report.name.ilike(f"%{f_q}%")
        ))
    if f_date_from:
        try:
            query = query.filter(
                AccessLog.accessed_at >= datetime.strptime(f_date_from, "%Y-%m-%d")
            )
        except Exception:
            pass
    if f_date_to:
        try:
            query = query.filter(
                AccessLog.accessed_at < datetime.strptime(f_date_to, "%Y-%m-%d") + timedelta(days=1)
            )
        except Exception:
            pass

    logs   = query.order_by(AccessLog.accessed_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Data/Hora", "Usuário", "Email", "Perfil", "Relatório", "IP"])
    for log, u, r in logs:
        writer.writerow([
            log.accessed_at.strftime("%d/%m/%Y %H:%M:%S"),
            u.name, u.email, u.role, r.name,
            log.ip_address or ""
        ])
    filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@admin_logs_bp.route("/admin/analytics")
@jwt_required()
def admin_analytics():
    ctx       = admin_logs_bp.ctx
    db        = ctx["db"]
    User      = ctx["User"]
    Report    = ctx["Report"]
    Role      = ctx["Role"]
    AccessLog = ctx["AccessLog"]
    user_id   = int(get_jwt_identity())
    user      = db.session.get(User, user_id)
    if not check_module_access(ctx, user, "logs"):
        return redirect(url_for("dashboard.dashboard"))

    # ── Filtros ──────────────────────────────────────────────────
    f_days       = request.args.get("days",       "").strip()
    f_date_from  = request.args.get("date_from",  "").strip()
    f_date_to_an = request.args.get("date_to",    "").strip()
    f_user       = request.args.get("user_id",    "").strip()
    f_role       = request.args.get("role",       "").strip()
    f_report     = request.args.get("report_id",  "").strip()
    hoje         = datetime.now(BRASILIA).date()

    # Modo customizado tem prioridade sobre período fixo
    if f_date_from and f_date_to_an:
        try:
            data_ini = datetime.strptime(f_date_from,  "%Y-%m-%d").date()
            data_fim = datetime.strptime(f_date_to_an, "%Y-%m-%d").date()
            # Garante que data_fim >= data_ini
            if data_fim < data_ini:
                data_ini, data_fim = data_fim, data_ini
            f_days = "custom"
        except Exception:
            data_ini     = hoje - timedelta(days=30)
            data_fim     = hoje
            f_days       = "30"
            f_date_from  = ""
            f_date_to_an = ""
    else:
        f_days_int = int(f_days) if f_days.isdigit() else 30
        if f_days_int not in [1, 7, 15, 30, 60, 90]:
            f_days_int = 30
        f_days       = str(f_days_int)
        data_ini     = hoje if f_days_int == 1 else hoje - timedelta(days=f_days_int)
        data_fim     = hoje
        f_date_from  = ""
        f_date_to_an = ""

    # ── Filtro de role → lista de IDs ────────────────────────────
    user_ids_role = None
    if f_role:
        user_ids_role = [u.id for u in User.query.filter_by(role=f_role).all()]

    # ── Helper para aplicar filtros em qualquer query ─────────────
    def apply_filters(q):
        q = q.filter(
            AccessLog.accessed_at >= data_ini,
            AccessLog.accessed_at <  data_fim + timedelta(days=1)
        )
        if f_user:                     q = q.filter(AccessLog.user_id == int(f_user))
        if f_report:                   q = q.filter(AccessLog.report_id == int(f_report))
        if user_ids_role is not None:  q = q.filter(AccessLog.user_id.in_(user_ids_role))
        return q

    # ── Cards de resumo ──────────────────────────────────────────
    total_periodo   = apply_filters(AccessLog.query).count()
    total_hoje      = AccessLog.query.filter(cast(AccessLog.accessed_at, Date) == hoje).count()
    total_semana    = AccessLog.query.filter(AccessLog.accessed_at >= hoje - timedelta(days=7)).count()
    usuarios_ativos = db.session.query(func.count(func.distinct(AccessLog.user_id)))\
        .filter(AccessLog.accessed_at >= data_ini).scalar()

    # ── Acessos por dia ──────────────────────────────────────────
    dia_q    = apply_filters(db.session.query(
        cast(AccessLog.accessed_at, Date).label('dia'),
        func.count().label('total')
    ))
    dias_map = {str(r.dia): r.total for r in
                dia_q.group_by(cast(AccessLog.accessed_at, Date)).order_by('dia').all()}
    num_dias    = max((data_fim - data_ini).days + 1, 1)
    acessos_dia = [
        {"dia": str(data_ini + timedelta(days=i)),
         "total": dias_map.get(str(data_ini + timedelta(days=i)), 0)}
        for i in range(num_dias)
    ]

    # ── Top relatórios ───────────────────────────────────────────
    top_q = apply_filters(db.session.query(
        Report.id, Report.name, func.count(AccessLog.id).label('total')
    ).join(AccessLog, AccessLog.report_id == Report.id))
    top_reports = [{"id": r.id, "name": r.name, "total": r.total}
                   for r in top_q.group_by(Report.id, Report.name)
                               .order_by(func.count(AccessLog.id).desc()).limit(10).all()]

    # ── Top usuários ─────────────────────────────────────────────
    top_u_q = apply_filters(db.session.query(
        User.id, User.name, User.role, func.count(AccessLog.id).label('total')
    ).join(AccessLog, AccessLog.user_id == User.id))
    top_users = [{"id": u.id, "name": u.name, "role": u.role, "total": u.total}
                 for u in top_u_q.group_by(User.id, User.name, User.role)
                               .order_by(func.count(AccessLog.id).desc()).limit(10).all()]

    # ── Por hora ─────────────────────────────────────────────────
    hora_q    = apply_filters(db.session.query(
        func.extract('hour', AccessLog.accessed_at).label('hora'),
        func.count().label('total')
    ))
    horas_map = {int(r.hora): r.total for r in hora_q.group_by('hora').all()}
    acessos_hora = [{"hora": f"{h:02d}h", "total": horas_map.get(h, 0)} for h in range(24)]

    # ── Por dia da semana ────────────────────────────────────────
    sem_q   = apply_filters(db.session.query(
        func.extract('dow', AccessLog.accessed_at).label('dow'),
        func.count().label('total')
    ))
    dow_map = {int(r.dow): r.total for r in sem_q.group_by('dow').all()}
    acessos_semana = [
        {"dia": nome, "total": dow_map.get((i + 1) % 7, 0)}
        for i, nome in enumerate(['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'])
    ]

    # ── Por perfil ───────────────────────────────────────────────
    perf_q       = apply_filters(db.session.query(
        User.role, func.count(AccessLog.id).label('total')
    ).join(AccessLog, AccessLog.user_id == User.id))
    roles_labels = {r.key: r.label for r in Role.query.all()}
    acessos_perfil = [
        {"role": roles_labels.get(r.role, r.role), "role_key": r.role, "total": r.total}
        for r in perf_q.group_by(User.role).all()
    ]

    return render_template("admin_analytics.html",
        user=user,
        total_hoje=total_hoje,
        total_semana=total_semana,
        total_periodo=total_periodo,
        usuarios_ativos=usuarios_ativos,
        acessos_dia=acessos_dia,
        top_reports=top_reports,
        top_users=top_users,
        acessos_hora=acessos_hora,
        acessos_semana=acessos_semana,
        acessos_perfil=acessos_perfil,
        all_users=User.query.filter_by(active=True).order_by(User.name).all(),
        all_reports=Report.query.filter_by(active=True).order_by(Report.name).all(),
        all_roles=Role.query.filter_by(active=True).order_by(Role.label).all(),
        f_days=f_days,
        f_date_from=f_date_from,
        f_date_to=f_date_to_an,
        f_user=f_user,
        f_role=f_role,
        f_report=f_report,
        data_ini=str(data_ini),
        data_fim=str(data_fim),
    )