from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os
from datetime import timedelta

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_SECURE"] = False
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)

db = SQLAlchemy(app)
jwt = JWTManager(app)

from models import init_models, create_tables
User, Report, ReportRLS, Group, ReportGroup, Permission, AccessLog = init_models(db)

from routes import init_routes
init_routes(app, db, User, Report, ReportRLS, Group, ReportGroup, Permission, AccessLog)

if __name__ == "__main__":
    with app.app_context():
        create_tables(db)
    app.run(debug=True, host="0.0.0.0", port=5000)