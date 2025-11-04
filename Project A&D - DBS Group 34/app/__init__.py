from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config


db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        db.create_all()  # Create database tables for our data models
    return app
if __name__ == '__main__':
    # 1. Call the function to create and configure the application
    app = create_app()
    
    # 2. Run the Flask development server
    app.run(debug=True)