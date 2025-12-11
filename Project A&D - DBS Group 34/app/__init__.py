from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from supabase import create_client, Client
from .config import Config
import click
import logging
import warnings

# Onderdruk yfinance/urllib3 HTTP warnings (404 errors zijn normaal als ticker niet bestaat)
logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
# Onderdruk ook Python warnings voor HTTP errors
warnings.filterwarnings('ignore', message='.*HTTP Error.*')
warnings.filterwarnings('ignore', message='.*quoteSummary.*')

db = SQLAlchemy()
migrate = Migrate()
supabase: Client | None = None
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
    
    # Voeg de periodieke taken toe
    # Zorg ervoor dat dit alleen gebeurt als de scheduler nog niet draait
    if not scheduler.running:
        # Live prijzen: elke 5 minuten (voor current_price en day_change_pct)
        scheduler.add_job(
            id='update_prices_job', 
            func=lambda: update_portfolio_prices(app), 
            trigger='interval', 
            minutes=5, 
            max_instances=1,
            misfire_grace_time=30
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

    # Template filters registreren (functies zijn nu in routes.py)
    from .routes import format_currency, format_number, format_percentage, format_date, format_transaction_date
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['number'] = format_number
    app.jinja_env.filters['percentage'] = format_percentage
    app.jinja_env.filters['date_format'] = format_date
    app.jinja_env.filters['transaction_date'] = format_transaction_date
    
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
    
    @app.context_processor
    def inject_file_icon():
        """Maakt file icon functie beschikbaar in templates."""
        from .routes import _get_file_icon
        return dict(get_file_icon=_get_file_icon)
    
    @app.context_processor
    def inject_utils():
        """Maakt utility functies beschikbaar in templates."""
        from .routes import format_currency, format_number, format_percentage, format_date
        return dict(
            format_currency=format_currency,
            format_number=format_number,
            format_percentage=format_percentage,
            format_date=format_date
        )

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

    @app.cli.command("update-prices")
    def update_prices_cli():
        """Manually trigger the portfolio price update job."""
        click.echo("Updating portfolio prices...")
        try:
            update_portfolio_prices(app)
            click.echo("✓ Portfolio prices updated successfully!")
        except Exception as e:
            click.echo(f"✗ Error updating prices: {e}", err=True)
            raise


    return app
