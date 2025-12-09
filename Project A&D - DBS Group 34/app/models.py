from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text # Needed for text() function for DEFAULT values
from datetime import datetime
from enum import Enum

def get_current_year():
    """Helper functie om huidige jaar te krijgen"""
    return datetime.now().year

# --- Enums voor Type Safety ---

class Sector(Enum):
    """Sector enum voor analisten"""
    CONSUMER_HEALTH = (1, "Cons. & Health")
    INDUSTRIAL_ENERGY_RM = (2, "Ind., E. & R.M.")
    RE_FINANCIAL_HOLDING = (3, "RE, F. & Hold.")
    TECH = (4, "Tech")
    
    def __init__(self, num, display_name):
        self.num = num
        self.display_name = display_name
    
    @classmethod
    def get_display_name(cls, sector_num):
        """Haal display naam op voor sector nummer"""
        for sector in cls:
            if sector.num == sector_num:
                return sector.display_name
        return f"Sector {sector_num}"
    
    @classmethod
    def get_all_options(cls):
        """Haal alle opties op voor dropdown"""
        return [(sector.display_name, sector.display_name) for sector in cls]

class BoardFunction(Enum):
    """Board functie enum"""
    VOORZITTER = (1, "Voorzitter")
    VICE_VOORZITTER = (2, "Vice-voorzitter")
    PORTFOLIO_MANAGER = (3, "Portfolio Manager")
    FUND_ADMINISTRATOR = (4, "Fund Administrator")
    MARKETING = (5, "Marketing")
    PUBLIC_RELATIONS = (6, "Public Relations")
    
    def __init__(self, num, display_name):
        self.num = num
        self.display_name = display_name
    
    @classmethod
    def get_display_name(cls, function_code):
        """Haal display naam op voor functie code"""
        for func in cls:
            if func.num == function_code:
                return func.display_name
        return f'Functie {function_code}'

class TransactionType(Enum):
    """Transaction type enum"""
    BUY = "BUY"
    SELL = "SELL"
    
    @classmethod
    def is_valid(cls, value):
        """Check of waarde een geldig transaction type is"""
        return any(choice.value == value.upper() for choice in cls)
    
    @classmethod
    def get_all_options(cls):
        """Haal alle opties op voor dropdown"""
        return [(choice.value, choice.value) for choice in cls]

class AssetClass(Enum):
    """Asset class enum"""
    STOCK = "Stock"
    ETF = "ETF"
    BOND = "Bond"
    CASH = "Cash"
    CRYPTO = "Crypto"
    OTHER = "Other"
    
    @classmethod
    def is_valid(cls, value):
        """Check of waarde een geldig asset class is"""
        return any(choice.value == value for choice in cls)
    
    @classmethod
    def get_all_options(cls):
        """Haal alle opties op voor dropdown"""
        return [(choice.value, choice.value) for choice in cls]

class Currency(Enum):
    """Currency enum"""
    EUR = "EUR"
    USD = "USD"
    CAD = "CAD"
    DKK = "DKK"
    
    @classmethod
    def is_valid(cls, value):
        """Check of waarde een geldige currency is"""
        return any(choice.value == value.upper() for choice in cls)
    
    @classmethod
    def get_all_options(cls):
        """Haal alle opties op voor dropdown"""
        return [(choice.value, choice.value) for choice in cls]

# --- Iv_club Table ---
class IvClub(db.Model):
    __tablename__ = 'Iv_club'
    club_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    location = db.Column(db.String)
    club_name = db.Column(db.String)
    
    # Optional: Relationship to access members easily
    members = db.relationship('Member', backref='club', lazy='dynamic')
    
# --- events Table ---
class Event(db.Model):
    __tablename__ = 'events'
    event_number = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_name = db.Column(db.String(255), nullable=False)
    event_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    location = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    
# --- files Table ---
class File(db.Model):
    __tablename__ = 'files'
    files_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    file_date = db.Column(db.DateTime(timezone=True), nullable=False)
    template = db.Column(db.Text)
    post_analyses = db.Column(db.Text)

# --- file_items Table (voor folders en bestanden) ---
class FileItem(db.Model):
    __tablename__ = 'file_items'
    item_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # 'folder' of 'file'
    parent_id = db.Column(db.BigInteger, db.ForeignKey('file_items.item_id'), nullable=True)  # NULL = root level
    file_path = db.Column(db.Text, nullable=True)  # Voor files: pad naar bestand
    file_size = db.Column(db.BigInteger, nullable=True)  # Voor files: grootte in bytes
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    created_by = db.Column(db.BigInteger, db.ForeignKey('members.id'), nullable=True)
    
    # Self-referential relationship voor folder structuur
    parent = db.relationship('FileItem', remote_side=[item_id], backref='children')
    
    # Relationship to creator
    creator = db.relationship('Member', foreign_keys=[created_by], backref='created_files')
    
# --- Unified members Table (Includes all roles: board, analist, lid, kapitaalverschaffers, oud) ---
class Member(UserMixin, db.Model):
    __tablename__ = 'members'
    
    # ID is 6 cijfers: [ROL][FUNCTIE/SECTOR/NUMMER][JAAR]
    # 0 = board, 1 = analist, 2 = lid, 3 = kapitaalverschaffers, 4 = oud
    member_id = db.Column('id', db.BigInteger, primary_key=True)  # Geen autoincrement - custom generatie
    
    join_date = db.Column(db.Integer, nullable=False, default=get_current_year)  # Jaar als integer (bijv. 2025)
    sector = db.Column(db.Text)  # Voor analisten: sector nummer
    voting_right = db.Column(db.Text)
    member_name = db.Column(db.Text)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True) 
    password_hash = db.Column(db.String(255))  # Increased from 128 to 255 for scrypt hashes
    
    club_id = db.Column(db.BigInteger, db.ForeignKey('Iv_club.club_id'))
    
    guided_by = db.Column(UUID(as_uuid=True), default=text('gen_random_uuid()'))
    
    # Extra velden voor backward compatibility en extra info
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())  # Voor board members
    
    def get_id(self):
        return str(self.member_id)
        
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # --- ID-gebaseerde rol-detectie methodes ---
    
    def get_role(self):
        """Bepaalt rol op basis van eerste cijfer van ID"""
        if self.member_id is None:
            return None
        id_str = str(self.member_id).zfill(6)  # Zorg voor 6 cijfers
        if len(id_str) < 1:
            return None
        first_digit = int(id_str[0])
        
        role_map = {
            0: 'board',
            1: 'analist',
            2: 'lid',
            3: 'kapitaalverschaffers',
            4: 'oud_bestuur_analisten'
        }
        return role_map.get(first_digit, 'lid')  # default naar lid
    
    def get_year(self):
        """Haalt jaar uit laatste 3 cijfers van ID"""
        if self.member_id is None:
            return None
        id_str = str(self.member_id).zfill(6)
        if len(id_str) < 3:
            return None
        year_suffix = int(id_str[-3:])
        # Converteer naar volledig jaar (025 -> 2025)
        if year_suffix < 100:
            return 2000 + year_suffix
        return year_suffix
    
    def get_join_year(self):
        """Geeft join_date terug als jaar (voor backward compatibility)"""
        if self.join_date:
            return self.join_date
        # Fallback naar jaar uit ID als join_date niet is ingesteld
        return self.get_year()
    
    def get_board_function(self):
        """Voor board members: haalt functie nummer (001-006)"""
        if self.get_role() != 'board':
            return None
        id_str = str(self.member_id).zfill(6)
        if len(id_str) < 3:
            return None
        function_code = int(id_str[1:3])
        return function_code
    
    def get_board_function_name(self):
        """Voor board members: haalt functie naam"""
        function_code = self.get_board_function()
        if function_code is None:
            return None
        
        # Gebruik BoardFunction enum indien beschikbaar
        try:
            return BoardFunction.get_display_name(function_code)
        except (NameError, AttributeError):
            # Fallback naar oude implementatie
            function_map = {
                1: 'Voorzitter',
                2: 'Vice-voorzitter',
                3: 'Portfolio Manager',
                4: 'Fund Administrator',
                5: 'Marketing',
                6: 'Public Relations'
            }
            return function_map.get(function_code, f'Functie {function_code}')
    
    def get_analist_sector(self):
        """Voor analisten: haalt sector nummer (1-4)"""
        if self.get_role() != 'analist':
            return None
        id_str = str(self.member_id).zfill(6)
        if len(id_str) < 3:
            return None
        return int(id_str[1])
    
    def get_analist_number_in_sector(self):
        """Voor analisten: haalt nummer binnen sector"""
        if self.get_role() != 'analist':
            return None
        id_str = str(self.member_id).zfill(6)
        if len(id_str) < 3:
            return None
        return int(id_str[2])
    
    def get_member_number_in_year(self):
        """Voor leden: haalt volgnummer in jaar (00-99)"""
        if self.get_role() != 'lid':
            return None
        id_str = str(self.member_id).zfill(6)
        if len(id_str) < 3:
            return None
        return int(id_str[1:3])
    
    def get_kapitaalverschaffer_number(self):
        """Voor kapitaalverschaffers: haalt uniek nummer"""
        if self.get_role() != 'kapitaalverschaffers':
            return None
        id_str = str(self.member_id).zfill(6)
        if len(id_str) < 3:
            return None
        return int(id_str[1:3])
    
    def is_board_member(self):
        return self.get_role() == 'board'
    
    def is_analist(self):
        return self.get_role() == 'analist'
    
    def is_lid(self):
        return self.get_role() == 'lid'
    
    def is_kapitaalverschaffer(self):
        return self.get_role() == 'kapitaalverschaffers'
    
    def is_oud_bestuur_analist(self):
        return self.get_role() == 'oud_bestuur_analisten'
    
    def has_access(self):
        """Bepaalt of gebruiker toegang heeft tot web-app"""
        role = self.get_role()
        # Alle rollen hebben toegang behalve mogelijk bepaalde edge cases
        return role in ['board', 'analist', 'lid', 'kapitaalverschaffers', 'oud_bestuur_analisten']
    
    def get_role_display_name(self):
        """Geeft display naam terug voor rol - gebruikt in templates"""
        role = self.get_role()
        
        if role == 'board':
            return self.get_board_function_name() or 'Bestuurslid'
        elif role == 'analist':
            sector_num = self.get_analist_sector()
            # Gebruik Sector enum indien beschikbaar
            try:
                if sector_num:
                    return f'Analist ({Sector.get_display_name(sector_num)})'
            except (NameError, AttributeError):
                pass
            # Fallback
            sector_names = {
                1: 'Analist (Cons. & Health)',
                2: 'Analist (Ind., E. & R.M.)',
                3: 'Analist (RE, F. & Hold.)',
                4: 'Analist (Tech)'
            }
            return sector_names.get(sector_num, f'Analist (Sector {sector_num})') if sector_num else 'Analist'
        elif role == 'lid':
            return 'Lid'
        elif role == 'kapitaalverschaffers':
            return 'Kapitaalverschaffer'
        elif role == 'oud_bestuur_analisten':
            if self.get_board_function_name():
                return f'Oud-{self.get_board_function_name()}'
            elif self.get_analist_sector():
                sector_num = self.get_analist_sector()
                # Gebruik Sector enum indien beschikbaar
                try:
                    if sector_num:
                        return f'Oud-Analist ({Sector.get_display_name(sector_num)})'
                except (NameError, AttributeError):
                    pass
                # Fallback
                sector_names = {
                    1: 'Oud-Analist (Cons. & Health)',
                    2: 'Oud-Analist (Ind., E. & R.M.)',
                    3: 'Oud-Analist (RE, F. & Hold.)',
                    4: 'Oud-Analist (Tech)'
                }
                return sector_names.get(sector_num, f'Oud-Analist (Sector {sector_num})') if sector_num else 'Oud-Analist'
            else:
                return 'Oud-Bestuurslid/Analist'
        else:
            return self.voting_right or 'Onbekend'


# --- ID Generatie Functies ---

def get_year_suffix(year=None):
    """Converteert jaar naar 3-cijferig suffix (2025 -> 025)"""
    if year is None:
        year = datetime.now().year
    return year % 1000


def generate_board_member_id(function_code, year=None):
    """
    Genereert ID voor board member
    Format: 0[FUNCTIE][JAAR]
    function_code: 1-6 (001-006)
    year: optioneel, default huidige jaar
    """
    year_suffix = get_year_suffix(year)
    # function_code moet 1-6 zijn, maar we gebruiken 001-006 format
    function_str = str(function_code).zfill(2)
    year_str = str(year_suffix).zfill(3)
    return int(f"0{function_str}{year_str}")


def generate_analist_id(sector, analist_number, year=None):
    """
    Genereert ID voor analist
    Format: 1[SECTOR][NUMMER][JAAR]
    sector: 1-4
    analist_number: nummer binnen sector (1-9, of meer)
    year: optioneel, default huidige jaar
    """
    year_suffix = get_year_suffix(year)
    sector_str = str(sector)
    analist_str = str(analist_number)
    year_str = str(year_suffix).zfill(3)
    return int(f"1{sector_str}{analist_str}{year_str}")


def generate_lid_id(member_number, year=None):
    """
    Genereert ID voor lid
    Format: 2[NUMMER][JAAR]
    member_number: 00-99 (volgnummer in jaar)
    year: optioneel, default huidige jaar
    """
    year_suffix = get_year_suffix(year)
    member_str = str(member_number).zfill(2)
    year_str = str(year_suffix).zfill(3)
    return int(f"2{member_str}{year_str}")


def generate_kapitaalverschaffer_id(verschaffer_number, year=None):
    """
    Genereert ID voor kapitaalverschaffer
    Format: 3[NUMMER][JAAR]
    verschaffer_number: uniek nummer (00-99)
    year: optioneel, default huidige jaar
    """
    year_suffix = get_year_suffix(year)
    verschaffer_str = str(verschaffer_number).zfill(2)
    year_str = str(year_suffix).zfill(3)
    return int(f"3{verschaffer_str}{year_str}")


def convert_to_oud_id(original_id):
    """
    Converteert een bestaand ID naar oud-bestuur/analist ID
    Verandert eerste cijfer naar 4
    Voorbeeld: 001025 -> 401025
    """
    if original_id is None:
        return None
    id_str = str(original_id).zfill(6)
    if len(id_str) < 6:
        return None
    # Verander eerste cijfer naar 4
    return int(f"4{id_str[1:]}")


def get_next_available_id(role, **kwargs):
    """
    Bepaalt het volgende beschikbare ID voor een bepaalde rol
    Controleert database voor bestaande IDs
    
    role: 'board', 'analist', 'lid', 'kapitaalverschaffers'
    kwargs: extra parameters afhankelijk van rol
    """
    year = kwargs.get('year', datetime.now().year)
    year_suffix = get_year_suffix(year)
    
    if role == 'board':
        function_code = kwargs.get('function_code', 1)
        # Check of dit ID al bestaat
        proposed_id = generate_board_member_id(function_code, year)
        while db.session.get(Member, proposed_id) is not None:
            # Als functie al bezet is, kan dit niet (elke functie is uniek per jaar)
            raise ValueError(f"Board functie {function_code} is al bezet voor jaar {year}")
        return proposed_id
    
    elif role == 'analist':
        sector = kwargs.get('sector', 1)
        # Zoek hoogste analist nummer in deze sector voor dit jaar
        existing = db.session.query(Member).filter(
            Member.member_id >= int(f"1{sector}0{year_suffix:03d}"),
            Member.member_id < int(f"1{sector+1}0{year_suffix:03d}")
        ).order_by(Member.member_id.desc()).first()
        
        if existing:
            existing_analist_num = existing.get_analist_number_in_sector()
            next_num = existing_analist_num + 1
        else:
            next_num = 1
        
        return generate_analist_id(sector, next_num, year)
    
    elif role == 'lid':
        # Zoek alle bestaande lid nummers voor dit jaar
        existing_members = db.session.query(Member).filter(
            Member.member_id >= int(f"200{year_suffix:03d}"),
            Member.member_id < int(f"300{year_suffix:03d}")
        ).all()
        
        # Verzamel alle gebruikte nummers (0-99)
        used_numbers = set()
        for member in existing_members:
            member_num = member.get_member_number_in_year()
            if member_num is not None and 0 <= member_num <= 99:
                used_numbers.add(member_num)
        
        # Vind het eerste beschikbare nummer (0-99)
        next_num = None
        for num in range(100):  # 0 tot en met 99
            if num not in used_numbers:
                next_num = num
                break
        
        # Als alle nummers gebruikt zijn (0-99), dan is het vol
        if next_num is None:
            raise ValueError(f"Maximum aantal leden (100) bereikt voor jaar {year}")
        
        return generate_lid_id(next_num, year)
    
    elif role == 'kapitaalverschaffers':
        # Zoek hoogste kapitaalverschaffer nummer voor dit jaar
        existing = db.session.query(Member).filter(
            Member.member_id >= int(f"300{year_suffix:03d}"),
            Member.member_id < int(f"400{year_suffix:03d}")
        ).order_by(Member.member_id.desc()).first()
        
        if existing:
            existing_num = existing.get_kapitaalverschaffer_number()
            next_num = existing_num + 1
        else:
            next_num = 0
        
        if next_num > 99:
            raise ValueError(f"Maximum aantal kapitaalverschaffers (100) bereikt voor jaar {year}")
        
        return generate_kapitaalverschaffer_id(next_num, year)
    
    else:
        raise ValueError(f"Onbekende rol: {role}")

    
# --- portfolio Table ---
class Portfolio(db.Model):
    __tablename__ = 'portfolio'
    portfolio_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    portfolio_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    # Note: double precision maps to db.Float
    profit_loss = db.Column('profit&loss', db.Float)
    
    # Relationship to positions
    positions = db.relationship('Position', backref='portfolio', lazy='dynamic', cascade='all, delete-orphan')
    
# --- positions Table ---
class Position(db.Model):
    __tablename__ = 'positions'
    pos_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pos_name = db.Column(db.Text, nullable=False)
    pos_type = db.Column(db.Text)
    pos_quantity = db.Column(db.Integer)  # Changed to Integer
    pos_value = db.Column(db.Float)  # Renamed from pos_amount
    pos_ticker = db.Column(db.String(50))  # Added
    pos_sector = db.Column(db.String(100))  # Added
    current_price = db.Column(db.Float)  # Huidige share price (gecached)
    day_change_pct = db.Column(db.Float)  # Dagverandering percentage (gecached)
    portfolio_id = db.Column(db.BigInteger, db.ForeignKey('portfolio.portfolio_id'), nullable=False)
    
# --- transactions Table ---
class Transaction(db.Model):
    __tablename__ = 'transactions'
    transaction_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    transaction_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    transaction_amount = db.Column(db.Float)
    transaction_quantity = db.Column(db.Float)
    transaction_type = db.Column(db.Text)
    transaction_ticker = db.Column(db.String(50))  # Ticker symbol
    transaction_currency = db.Column(db.String(10))  # Currency (EUR, USD, etc.)
    transaction_share_price = db.Column(db.Float)  # Price per share
    asset_name = db.Column(db.Text)  # Asset name
    asset_type = db.Column(db.Text)  # Voor backward compatibility (same as asset_class)
    sector = db.Column(db.String(100))  # Sector van het asset
    asset_class = db.Column(db.String(100))  # Asset class (bijv. Stock, Bond, etc.)
    
    
# --- voting_proposal Table ---
class VotingProposal(db.Model):
    __tablename__ = 'voting_proposal'
    proposal_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    proposal_date = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    proposal_type = db.Column(db.Text)
    minimum_requirements = db.Column(db.Text)
    stock_name = db.Column(db.String(255))  # Bijv. "Stock XYZ"
    deadline = db.Column(db.DateTime(timezone=True), nullable=False)  # Deadline voor stemmen
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    
    # Relationship to votes
    votes = db.relationship('Vote', backref='proposal', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_vote_counts(self):
        """Helper method om vote counts te krijgen zonder extra queries"""
        votes_list = self.votes.all()
        return {
            'total': len(votes_list),
            'voor': sum(1 for v in votes_list if v.vote_option.lower() == 'voor'),
            'tegen': sum(1 for v in votes_list if v.vote_option.lower() == 'tegen'),
            'onthouding': sum(1 for v in votes_list if v.vote_option.lower() == 'onthouding')
        }
    
    def has_user_voted(self, user_id):
        """Check of gebruiker al gestemd heeft"""
        if not user_id:
            return False
        return self.votes.filter_by(member_id=user_id).first() is not None

# --- votes Table ---
class Vote(db.Model):
    __tablename__ = 'votes'
    vote_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    proposal_id = db.Column(db.BigInteger, db.ForeignKey('voting_proposal.proposal_id'), nullable=False)
    member_id = db.Column(db.BigInteger, db.ForeignKey('members.id'), nullable=False)
    vote_option = db.Column(db.String(20), nullable=False)  # 'voor', 'tegen', 'onthouding'
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    
    # Relationships met backref
    member = db.relationship('Member', backref='member_votes')
    
    # Unique constraint: een member kan maar één keer stemmen per proposal
    __table_args__ = (db.UniqueConstraint('proposal_id', 'member_id', name='unique_member_proposal_vote'),)
    
    def to_dict(self):
        """Convert vote to dictionary for JSON serialization"""
        return {
            'vote_id': self.vote_id,
            'proposal_id': self.proposal_id,
            'member_id': self.member_id,
            'vote_option': self.vote_option,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())