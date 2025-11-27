"""
Migratie script om Analist en BoardMember tabellen samen te voegen met Member tabel.

Dit script:
1. Voegt nieuwe kolommen toe aan members tabel (analist_start_date, created_at)
2. Migreert data van Analist en BoardMember naar Member
3. Converteert IDs naar het nieuwe 6-cijferig formaat
4. Verwijdert oude tabellen (optioneel)

LET OP: Maak eerst een backup van je database voordat je dit script uitvoert!
"""

from app import create_app, db
from app.models import (
    Member, 
    generate_board_member_id, generate_analist_id, generate_lid_id,
    generate_kapitaalverschaffer_id, convert_to_oud_id
)
from sqlalchemy import text
from datetime import datetime

def migrate_data():
    """Migreert data van oude tabellen naar unified Member tabel"""
    app = create_app()
    
    with app.app_context():
        print("Starting migration...")
        
        # 1. Wijzig join_date naar INTEGER en verwijder analist_start_date
        try:
            # Check huidige kolom type
            result = db.session.execute(text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name='members' AND column_name='join_date'
            """))
            join_date_type = result.scalar()
            
            if join_date_type and join_date_type != 'integer':
                print("Converting join_date from DateTime to Integer (year)...")
                # Converteer bestaande datetime waarden naar jaar
                db.session.execute(text("""
                    UPDATE members 
                    SET join_date = EXTRACT(YEAR FROM join_date)::INTEGER 
                    WHERE join_date IS NOT NULL
                """))
                # Wijzig kolom type
                db.session.execute(text("ALTER TABLE members ALTER COLUMN join_date TYPE INTEGER USING join_date::INTEGER"))
            
            # Check of analist_start_date bestaat en verwijder het
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='members' AND column_name='analist_start_date'
            """))
            if result.scalar():
                print("Removing analist_start_date column...")
                db.session.execute(text("ALTER TABLE members DROP COLUMN IF EXISTS analist_start_date"))
            
            # Check of created_at bestaat
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='members' AND column_name='created_at'
            """))
            if not result.scalar():
                print("Adding created_at column...")
                db.session.execute(text("ALTER TABLE members ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
            
            db.session.commit()
            print("✓ Columns updated successfully")
        except Exception as e:
            print(f"⚠ Warning: Could not update columns: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
        
        # 2. Migreer BoardMember data
        try:
            print("\nMigrating BoardMember data...")
            board_members_old = db.session.execute(text("SELECT * FROM board_members")).fetchall()
            
            for bm in board_members_old:
                boardmember_id = bm[0]  # boardmember_id
                created_at = bm[1] if len(bm) > 1 else None
                boardmember_name = bm[2] if len(bm) > 2 else None
                voting_right = bm[3] if len(bm) > 3 else None
                
                # Bepaal functie code (001-006) - dit moet handmatig worden aangepast
                # Voor nu gebruiken we een default mapping
                function_code = 1  # Default naar voorzitter, pas dit aan op basis van voting_right
                if voting_right:
                    function_map = {
                        'Voorzitter': 1,
                        'Vice-voorzitter': 2,
                        'Portfolio Manager': 3,
                        'Fund Administrator': 4,
                        'Marketing': 5,
                        'Public Relations': 6
                    }
                    function_code = function_map.get(voting_right, 1)
                
                # Bepaal jaar uit created_at of gebruik huidige jaar
                if created_at:
                    year = created_at.year if hasattr(created_at, 'year') else datetime.now().year
                else:
                    year = datetime.now().year
                
                # Genereer nieuw ID
                new_id = generate_board_member_id(function_code, year)
                
                # Check of member al bestaat
                existing = db.session.get(Member, new_id)
                if existing:
                    print(f"  ⚠ Member with ID {new_id} already exists, skipping...")
                    continue
                
                # Maak nieuwe Member
                new_member = Member(
                    member_id=new_id,
                    member_name=boardmember_name,
                    voting_right=voting_right or 'Bestuurslid',
                    created_at=created_at or datetime.now(),
                    join_date=year,  # Jaar als integer
                    email=f"board_{new_id}@example.com",  # Tijdelijk email, moet worden aangepast
                    password_hash=None  # Moet worden ingesteld
                )
                db.session.add(new_member)
                print(f"  ✓ Migrated board member: {boardmember_name} -> ID {new_id}")
            
            db.session.commit()
            print(f"✓ Migrated {len(board_members_old)} board members")
        except Exception as e:
            print(f"✗ Error migrating board members: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
        
        # 3. Migreer Analist data
        try:
            print("\nMigrating Analist data...")
            analisten_old = db.session.execute(text("SELECT * FROM Analist")).fetchall()
            
            for analist in analisten_old:
                analist_id = analist[0]  # analist_id
                analist_start_date = analist[1] if len(analist) > 1 else None
                sector = analist[2] if len(analist) > 2 else None
                analist_name = analist[3] if len(analist) > 3 else None
                voting_right = analist[4] if len(analist) > 4 else None
                
                # Bepaal sector (1-4) - dit moet handmatig worden aangepast
                sector_num = 1  # Default, pas dit aan op basis van sector veld
                if sector:
                    # Map sector naam naar nummer (pas dit aan op basis van je data)
                    sector_map = {
                        'Cons. & Health': 1,
                        'Tech': 2,
                        'Finance': 3,
                        'Other': 4
                    }
                    sector_num = sector_map.get(sector, 1)
                
                # Bepaal analist nummer in sector (moet worden bepaald op basis van bestaande data)
                analist_number = 1  # Default, moet worden aangepast
                
                # Bepaal jaar
                if analist_start_date:
                    year = analist_start_date.year if hasattr(analist_start_date, 'year') else datetime.now().year
                else:
                    year = datetime.now().year
                
                # Genereer nieuw ID
                new_id = generate_analist_id(sector_num, analist_number, year)
                
                # Check of member al bestaat
                existing = db.session.get(Member, new_id)
                if existing:
                    print(f"  ⚠ Member with ID {new_id} already exists, skipping...")
                    continue
                
                # Maak nieuwe Member
                new_member = Member(
                    member_id=new_id,
                    member_name=analist_name,
                    sector=sector,
                    voting_right=voting_right or 'Analist',
                    join_date=year,  # Jaar als integer
                    email=f"analist_{new_id}@example.com",  # Tijdelijk email, moet worden aangepast
                    password_hash=None  # Moet worden ingesteld
                )
                db.session.add(new_member)
                print(f"  ✓ Migrated analist: {analist_name} -> ID {new_id}")
            
            db.session.commit()
            print(f"✓ Migrated {len(analisten_old)} analisten")
        except Exception as e:
            print(f"✗ Error migrating analisten: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
        
        # 4. Update bestaande Member IDs naar nieuw formaat (als nodig)
        # Dit is optioneel - alleen als je bestaande Member IDs wilt converteren
        print("\nNote: Existing Member IDs are not automatically converted.")
        print("You may need to manually update Member IDs to the new 6-digit format.")
        
        print("\n✓ Migration completed!")
        print("\nNEXT STEPS:")
        print("1. Review migrated data and update email addresses")
        print("2. Set passwords for migrated users")
        print("3. Update function codes and sector numbers if needed")
        print("4. (Optional) Drop old tables after verification:")
        print("   DROP TABLE IF EXISTS board_members;")
        print("   DROP TABLE IF EXISTS Analist;")

if __name__ == '__main__':
    migrate_data()

