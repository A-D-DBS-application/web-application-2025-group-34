import os
from pathlib import Path

# Bepaal base directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Config: 
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'gr8t3rth4nth3s3cur3k3y'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI') or 'postgresql://postgres.reexofzxklgbyxkwaonu:4JSSUixyNlY51wWw@aws-1-eu-north-1.pooler.supabase.com:6543/postgres'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Supabase credentials (haal uit environment variabelen of zet hier direct)
    SUPABASE_URL = os.environ.get('SUPABASE_URL') or 'https://reexofzxklgbyxkwaonu.supabase.co'
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY') or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJlZXhvZnp4a2xnYnl4a3dhb251Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA4OTM1OTksImV4cCI6MjA3NjQ2OTU5OX0.ZIKT_04K3yElT6VEhR_e61_7b10AZ7Ock0qlWVb3sKU'  # Zet hier je Supabase anon key
    SUPABASE_BUCKET = os.environ.get('SUPABASE_BUCKET') or 'files'  # Naam van de Supabase storage bucket
    
    # Upload configuration
    UPLOAD_FOLDER = BASE_DIR / 'uploads' / 'files'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_EXTENSIONS = {'zip', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
    
    # Zorg dat upload folder bestaat (voor backwards compatibility)
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    