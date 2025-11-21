from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from supabase import create_client, Client
from .config import Config
import os 
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
supabase: Client | None = None
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Database setup
    db.init_app(app)
    migrate.init_app(app, db)

    from . import models # maakt alle tabellen

    # Supabase setup
    global supabase
    supabase_url = app.config.get("SUPABASE_URL")
    supabase_key = app.config.get("SUPABASE_KEY")
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
    else:
        print("WARNING: Supabase credentials are not configured; continuing without Supabase.")
        supabase = None

    # Blueprint register
    from .routes import main
    app.register_blueprint(main)

    return app
