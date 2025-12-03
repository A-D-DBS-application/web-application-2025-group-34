import os

class Config: 
    SECRET_KEY = 'gr8t3rth4nth3s3cur3k3y'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres.reexofzxklgbyxkwaonu:4JSSUixyNlY51wWw@aws-1-eu-north-1.pooler.supabase.com:6543/postgres'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Supabase credentials (haal uit environment variabelen of zet hier direct)
    SUPABASE_URL = os.environ.get('SUPABASE_URL') or 'https://reexofzxklgbyxkwaonu.supabase.co'
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY') or ''  # Zet hier je Supabase anon key
    