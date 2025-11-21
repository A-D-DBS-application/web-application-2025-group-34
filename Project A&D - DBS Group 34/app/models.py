from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text # Needed for text() function for DEFAULT values

# --- Analist Table ---
class Analist(db.Model):
    __tablename__ = 'Analist'
    analist_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    # Note: GENERATED ALWAYS AS IDENTITY maps cleanly to primary_key=True and autoincrement=True
    analist_start_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    sector = db.Column(db.Text)
    analist_name = db.Column(db.Text)
    voting_right = db.Column(db.Text)
    
# --- Iv_club Table ---
class IvClub(db.Model):
    __tablename__ = 'Iv_club'
    club_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    location = db.Column(db.String)
    club_name = db.Column(db.String)
    
    # Optional: Relationship to access members easily
    members = db.relationship('Member', backref='club', lazy='dynamic')
    
# --- board_members Table ---
class BoardMember(db.Model):
    __tablename__ = 'board_members'
    boardmember_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    boardmember_name = db.Column(db.Text)
    voting_right = db.Column(db.Text)
    
# --- events Table ---
class Event(db.Model):
    __tablename__ = 'events'
    event_number = db.Column(db.BigInteger, primary_key=True)
    
# --- files Table ---
class File(db.Model):
    __tablename__ = 'files'
    files_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    file_date = db.Column(db.DateTime(timezone=True), nullable=False)
    template = db.Column(db.Text)
    post_analyses = db.Column(db.Text)
    
# --- members Table (Includes Foreign Key) ---
class Member(db.Model):
    __tablename__ = 'members'
    
    # FIX: Gaat ervan uit dat de DB Primary Key 'id' heet. 
    # De Python-code blijft 'member_id' gebruiken als attribuutnaam.
    member_id = db.Column('id', db.BigInteger, primary_key=True, autoincrement=True) 
    
    join_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    sector = db.Column(db.Text)
    voting_right = db.Column(db.Text)
    member_name = db.Column(db.Text)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True) 
    password_hash = db.Column(db.String(128))
    
    # Foreign Key to IvClub (NU GECORRIGEERD)
    club_id = db.Column(db.BigInteger, db.ForeignKey('Iv_club.club_id'))
    
    # UUID Column (NU GECORRIGEERD)
    guided_by = db.Column(UUID(as_uuid=True), default=text('gen_random_uuid()'))
    
    # Vereist door Flask-Login
    def get_id(self):
        return str(self.member_id)
        
    # METHODEN VOOR WACHTWOORD-BEVEILIGING (blijven hetzelfde)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # Foreign Key to IvClub
    club_id = db.Column(db.BigInteger, db.ForeignKey('Iv_club.club_id'))
    
    # UUID Column: Requires 'from sqlalchemy.dialects.postgresql import UUID'
    # Note: Use server_default=text('gen_random_uuid()') to execute the function on the database side
    guided_by = db.Column(UUID(as_uuid=True), default=text('gen_random_uuid()'))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True) # E-mail als unieke login
    password_hash = db.Column(db.String(128))
    
    # Vereist door Flask-Login om de gebruiker te identificeren
    def get_id(self):
        return str(self.member_id)
        
    # Foreign Key to IvClub
    club_id = db.Column(db.BigInteger, db.ForeignKey('Iv_club.club_id'))
    
    # UUID Column: Requires 'from sqlalchemy.dialects.postgresql import UUID'
    guided_by = db.Column(UUID(as_uuid=True), default=text('gen_random_uuid()'))
    
    # METHODEN VOOR WACHTWOORD-BEVEILIGING
    def set_password(self, password):
        """ Hash het wachtwoord en sla de hash op. """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """ Controleer het opgegeven wachtwoord tegen de opgeslagen hash. """
        return check_password_hash(self.password_hash, password)
    
# --- portfolio Table ---
class Portfolio(db.Model):
    __tablename__ = 'portfolio'
    portfolio_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    portfolio_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    # Note: double precision maps to db.Float
    profit_loss = db.Column('profit&loss', db.Float)
    
# --- positions Table ---
class Position(db.Model):
    __tablename__ = 'positions'
    pos_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pos_name = db.Column(db.Text, nullable=False)
    pos_type = db.Column(db.Text)
    pos_quantity = db.Column(db.Float)
    pos_amount = db.Column(db.Float)
    
# --- transactions Table ---
class Transaction(db.Model):
    __tablename__ = 'transactions'
    transaction_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    transaction_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    transaction_amount = db.Column(db.Float)
    transaction_quantity = db.Column(db.Float)
    transaction_type = db.Column(db.Text)
    
# --- voting_proposal Table ---
class VotingProposal(db.Model):
    __tablename__ = 'voting_proposal'
    proposal_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    proposal_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    proposal_type = db.Column(db.Text)
    minimum_requirements = db.Column(db.Text)