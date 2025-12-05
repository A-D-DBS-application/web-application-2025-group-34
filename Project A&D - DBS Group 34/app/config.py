import os
from pathlib import Path

# Bepaal base directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Config: 
    SECRET_KEY = 'gr8t3rth4nth3s3cur3k3y'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres.reexofzxklgbyxkwaonu:4JSSUixyNlY51wWw@aws-1-eu-north-1.pooler.supabase.com:6543/postgres'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Supabase credentials (haal uit environment variabelen of zet hier direct)
    SUPABASE_URL = os.environ.get('SUPABASE_URL') or 'https://reexofzxklgbyxkwaonu.supabase.co'
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY') or ''  # Zet hier je Supabase anon key
    
    # Upload configuration
    UPLOAD_FOLDER = BASE_DIR / 'uploads' / 'files'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_EXTENSIONS = {'zip', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
    
    # Zorg dat upload folder bestaat
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    