from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from supabase import create_client, Client
from .config import Config
import os
from flask_login import LoginManager
import click

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

    @app.cli.command("create-member")
    @click.option("--name", prompt=True, help="Full name for the member.")
    @click.option("--email", prompt=True, help="Unique email used for login.")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password for the member.")
    @click.option("--sector", default="", help="Optional sector label.")
    @click.option("--voting-right", "voting_right", default="", help="Optional voting right description.")
    def create_member_cli(name, email, password, sector, voting_right):
        """Creates a single member account with a hashed password."""
        from .models import Member

        if db.session.execute(db.select(Member).where(Member.email == email)).scalar_one_or_none():
            click.echo(f"Member with email {email} already exists.")
            return

        member = Member(
            member_name=name,
            email=email,
            sector=sector if sector else None,
            voting_right=voting_right if voting_right else None,
        )
        member.set_password(password)
        db.session.add(member)
        db.session.commit()
        click.echo(f"Created member '{name}' with email '{email}'.")

    return app
