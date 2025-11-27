from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from supabase import create_client, Client
from .config import Config
import os
from flask_login import LoginManager
import click

db = SQLAlchemy()
migrate = Migrate()
supabase: Client | None = None
login_manager = LoginManager()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Database setup
    db.init_app(app)
    migrate.init_app(app, db)
    from .jobs import update_portfolio_prices
    
    # Configureer de scheduler (optioneel, maar goed voor opstart)
    app.config['SCHEDULER_API_ENABLED'] = False 
    
    scheduler.init_app(app)
    
    # Voeg de periodieke taak toe (draait elke 5 minuten)
    # Zorg ervoor dat dit alleen gebeurt als de scheduler nog niet draait
    if not scheduler.running:
        scheduler.add_job(
            id='update_prices_job', 
            func=update_portfolio_prices, 
            trigger='interval', 
            minutes=5, 
            max_instances=1, # Zorgt ervoor dat de taak niet dubbel loopt
            misfire_grace_time=30 # Wachttijd voor mislukte runs
        )
        scheduler.start()

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

    # Context processor voor globale template variabelen
    @app.context_processor
    def inject_member_count():
        """Maakt het aantal deelnemers beschikbaar in alle templates."""
        try:
            from .models import Member
            member_count = db.session.query(Member).count()
        except Exception:
            # Fallback als database niet beschikbaar is
            member_count = 0
        return dict(member_count=member_count)

    @app.cli.command("create-member")
    @click.option("--name", prompt=True, help="Full name for the member.")
    @click.option("--email", default=None, help="Optional email used for login.")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password for the member.")
    @click.option("--sector", default="", help="Optional sector label.")
    @click.option("--voting-right", "voting_right", default="", help="Optional voting right description.")
    def create_member_cli(name, email, password, sector, voting_right):
        """Creates a single member account with a hashed password."""
        from .models import Member

        if email and db.session.execute(db.select(Member).where(Member.email == email)).scalar_one_or_none():
            click.echo(f"Member with email {email} already exists.")
            return

        from datetime import datetime
        
        member = Member(
            member_name=name,
            email=email if email else None,
            sector=sector if sector else None,
            voting_right=voting_right if voting_right else None,
            join_date=datetime.now().year,  # Huidige jaar als default
        )
        member.set_password(password)
        db.session.add(member)
        db.session.commit()
        if email:
            click.echo(f"Created member '{name}' with email '{email}'.")
        else:
            click.echo(f"Created member '{name}' without email.")

    return app
