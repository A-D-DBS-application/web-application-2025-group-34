"""
Script om wachtwoorden in te stellen voor Member accounts op basis van ID-nummers.

Gebruik:
1. Via dictionary in code (zie voorbeeld hieronder)
2. Via CSV bestand
3. Via command line input
"""

from app import create_app, db
from app.models import Member
from sqlalchemy import text
import csv
import sys

def set_password_for_id(member_id, password):
    """Stelt wachtwoord in voor een specifiek ID"""
    app = create_app()
    
    with app.app_context():
        member = db.session.get(Member, member_id)
        if not member:
            print(f"⚠ Member met ID {member_id} niet gevonden")
            return False
        
        member.set_password(password)
        db.session.commit()
        print(f"✓ Wachtwoord ingesteld voor ID {member_id} ({member.member_name or 'Onbekend'})")
        return True

def set_passwords_from_dict(password_dict):
    """
    Stelt wachtwoorden in vanuit een dictionary
    Format: {member_id: password, ...}
    
    Voorbeeld:
    passwords = {
        001025: "wachtwoord123",
        111025: "analist_pass",
        201025: "lid_pass"
    }
    """
    app = create_app()
    
    with app.app_context():
        success_count = 0
        fail_count = 0
        
        for member_id, password in password_dict.items():
            try:
                member = db.session.get(Member, member_id)
                if not member:
                    print(f"⚠ Member met ID {member_id} niet gevonden")
                    fail_count += 1
                    continue
                
                member.set_password(password)
                success_count += 1
                print(f"✓ Wachtwoord ingesteld voor ID {member_id:06d} ({member.member_name or 'Onbekend'})")
            except Exception as e:
                print(f"✗ Fout bij ID {member_id}: {e}")
                fail_count += 1
        
        db.session.commit()
        print(f"\n✓ {success_count} wachtwoorden ingesteld")
        if fail_count > 0:
            print(f"⚠ {fail_count} wachtwoorden konden niet worden ingesteld")
        
        return success_count, fail_count

def set_passwords_from_csv(csv_file_path, delimiter=';'):
    """
    Stelt wachtwoorden in vanuit een CSV bestand
    
    CSV format met semicolon delimiter (;):
    id_nummer;password
    001025;wachtwoord123
    111025;analist_pass
    201025;lid_pass
    
    Of met komma delimiter:
    member_id,password
    001025,wachtwoord123
    """
    app = create_app()
    
    with app.app_context():
        success_count = 0
        fail_count = 0
        skipped_count = 0
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=delimiter)
                
                # Skip header als die bestaat
                first_row = next(reader, None)
                if not first_row:
                    print("✗ CSV bestand is leeg")
                    return 0, 0
                
                # Check of eerste rij een header is
                is_header = False
                id_col_index = 0
                password_col_index = 1
                
                if first_row[0].lower().replace('_', '').replace('-', '') in ['id', 'idnummer', 'memberid', 'member_id']:
                    is_header = True
                    # Bepaal kolom indices
                    for i, col in enumerate(first_row):
                        col_lower = col.lower().replace('_', '').replace('-', '')
                        if col_lower in ['id', 'idnummer', 'memberid', 'member_id']:
                            id_col_index = i
                        elif 'password' in col_lower or 'wachtwoord' in col_lower or 'pass' in col_lower:
                            password_col_index = i
                
                # Verwerk alle rijen (inclusief eerste als het geen header is)
                rows_to_process = [first_row] if not is_header else []
                rows_to_process.extend(reader)
                
                for row_num, row in enumerate(rows_to_process, start=2 if is_header else 1):
                    # Skip lege rijen
                    if not row or len(row) < 2 or not any(row):
                        skipped_count += 1
                        continue
                    
                    # Skip als ID of password leeg is
                    if id_col_index >= len(row) or password_col_index >= len(row):
                        skipped_count += 1
                        continue
                    
                    id_str = row[id_col_index].strip()
                    password = row[password_col_index].strip()
                    
                    if not id_str or not password:
                        skipped_count += 1
                        continue
                    
                    try:
                        # Parse ID (kan zijn: "1", "001025", "1025", etc.)
                        member_id = int(id_str)
                        
                        # Check of member bestaat - probeer eerst exacte match
                        member = db.session.get(Member, member_id)
                        
                        # Als niet gevonden, probeer met leading zeros (voor 6-cijferig formaat)
                        if not member and len(id_str) < 6:
                            # Probeer met leading zeros
                            padded_id = int(id_str.zfill(6))
                            member = db.session.get(Member, padded_id)
                            if member:
                                member_id = padded_id  # Gebruik de padded ID
                        
                        if not member:
                            # Laatste poging: zoek alle members en check of er een match is
                            all_members = db.session.query(Member).all()
                            found = False
                            for m in all_members:
                                if str(m.member_id) == id_str or str(m.member_id).lstrip('0') == id_str.lstrip('0'):
                                    member = m
                                    member_id = m.member_id
                                    found = True
                                    break
                            
                            if not found:
                                print(f"⚠ Regel {row_num}: Member met ID {id_str} (of {member_id:06d}) niet gevonden in database")
                                fail_count += 1
                                continue
                        
                        # Stel wachtwoord in
                        member.set_password(password)
                        success_count += 1
                        display_id = f"{member_id:06d}" if member_id >= 100000 else str(member_id)
                        print(f"✓ Regel {row_num}: Wachtwoord ingesteld voor ID {display_id} ({member.member_name or 'Onbekend'})")
                        
                    except ValueError:
                        print(f"✗ Regel {row_num}: Ongeldig ID formaat: '{id_str}'")
                        fail_count += 1
                    except Exception as e:
                        print(f"✗ Regel {row_num}: Fout bij ID {id_str}: {e}")
                        fail_count += 1
            
            db.session.commit()
            print(f"\n{'='*60}")
            print(f"✓ {success_count} wachtwoorden succesvol ingesteld")
            if fail_count > 0:
                print(f"⚠ {fail_count} wachtwoorden konden niet worden ingesteld")
            if skipped_count > 0:
                print(f"⊘ {skipped_count} rijen overgeslagen (leeg of ongeldig)")
            print(f"{'='*60}")
            
            return success_count, fail_count
            
        except FileNotFoundError:
            print(f"✗ Bestand niet gevonden: {csv_file_path}")
            print(f"   Zorg dat het pad correct is (absolute of relatief pad)")
            return 0, 0
        except Exception as e:
            print(f"✗ Fout bij lezen van CSV: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return 0, 0

def set_password_interactive():
    """Interactieve modus: vraag ID en wachtwoord"""
    app = create_app()
    
    with app.app_context():
        print("Interactieve wachtwoord instelling")
        print("Druk op Enter zonder input om te stoppen\n")
        
        while True:
            try:
                member_id_str = input("Voer ID nummer in (6 cijfers, of Enter om te stoppen): ").strip()
                if not member_id_str:
                    break
                
                member_id = int(member_id_str)
                password = input(f"Voer wachtwoord in voor ID {member_id:06d}: ").strip()
                
                if not password:
                    print("⚠ Wachtwoord mag niet leeg zijn")
                    continue
                
                member = db.session.get(Member, member_id)
                if not member:
                    print(f"⚠ Member met ID {member_id:06d} niet gevonden")
                    continue
                
                member.set_password(password)
                db.session.commit()
                print(f"✓ Wachtwoord ingesteld voor ID {member_id:06d} ({member.member_name or 'Onbekend'})\n")
                
            except ValueError:
                print("⚠ Ongeldig ID formaat. Gebruik alleen cijfers.\n")
            except KeyboardInterrupt:
                print("\n\nGestopt door gebruiker")
                break
            except Exception as e:
                print(f"✗ Fout: {e}\n")
                db.session.rollback()

def list_all_member_ids():
    """Helper functie: toont alle member ID's in de database"""
    app = create_app()
    
    with app.app_context():
        try:
            members = db.session.query(Member).order_by(Member.member_id.asc()).all()
            if not members:
                print("⚠ Geen members gevonden in database")
                return
            
            print(f"\nGevonden {len(members)} members in database:")
            print("-" * 60)
            for m in members:
                display_id = f"{m.member_id:06d}" if m.member_id >= 100000 else str(m.member_id)
                name = m.member_name or "Onbekend"
                has_password = "✓" if m.password_hash else "✗"
                print(f"  ID: {display_id:>8} | {name:30} | Wachtwoord: {has_password}")
            print("-" * 60)
        except Exception as e:
            print(f"✗ Fout bij ophalen van members: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Hoofdfunctie - kies je methode hier"""
    
    # ============================================
    # OPTIE 0: Toon alle member ID's (voor debugging)
    # ============================================
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_all_member_ids()
        return
    
    # ============================================
    # OPTIE 1: Via CSV bestand (AANBEVOLEN)
    # ============================================
    # Gebruik command line argument of pas pad aan
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        # Standaard pad - pas aan naar jouw bestand
        csv_file = r"c:\Users\jibbe\Downloads\passwords.csv"
        # Of gebruik relatief pad:
        # csv_file = "passwords.csv"
    
    print(f"Lezen van CSV bestand: {csv_file}")
    print(f"Delimiter: semicolon (;)\n")
    
    # Probeer eerst met semicolon, dan met komma
    success, fail = set_passwords_from_csv(csv_file, delimiter=';')
    if success == 0 and fail > 0:
        print("\nProberen met komma delimiter...")
        success, fail = set_passwords_from_csv(csv_file, delimiter=',')
    
    if success > 0:
        print(f"\n🎉 Klaar! {success} wachtwoorden zijn ingesteld.")
        print("Gebruikers kunnen nu inloggen met hun ID-nummer en wachtwoord.")
        return
    elif fail > 0:
        print(f"\n⚠ Let op: {fail} wachtwoorden konden niet worden ingesteld.")
        print("Controleer of de ID-nummers in de CSV overeenkomen met de database.")
    
    # ============================================
    # OPTIE 2: Via dictionary in code
    # ============================================
    # Pas deze dictionary aan met jouw ID's en wachtwoorden:
    passwords = {
        # Format: member_id: "wachtwoord"
        # 001025: "wachtwoord_voor_voorzitter",
        # 111025: "wachtwoord_voor_analist",
        # 201025: "wachtwoord_voor_lid",
        # ... voeg meer toe
    }
    
    if passwords:
        print("Wachtwoorden instellen vanuit dictionary...")
        set_passwords_from_dict(passwords)
        return
    
    # ============================================
    # OPTIE 3: Interactief (vraagt om input)
    # ============================================
    set_password_interactive()

if __name__ == '__main__':
    print("=" * 60)
    print("Wachtwoord Instelling Script")
    print("=" * 60)
    print("\nKies een methode in de main() functie:")
    print("1. Dictionary in code (snelste voor kleine aantallen)")
    print("2. CSV bestand (beste voor grote aantallen)")
    print("3. Interactief (handmatig invoeren)\n")
    print("=" * 60)
    print()
    
    main()

