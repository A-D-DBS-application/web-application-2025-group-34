# Migratie Commands - Stap voor Stap

## ⚠️ BELANGRIJK: Maak eerst een backup van je database!

### Stap 1: Database Backup (PostgreSQL)
```bash
# Als je PostgreSQL gebruikt, maak een backup:
pg_dump -U je_gebruikersnaam -d je_database_naam > backup_voor_migratie.sql

# Of via psql:
pg_dump je_database_naam > backup_voor_migratie.sql
```

### Stap 2: Activeer je virtual environment
```powershell
# In PowerShell (Windows):
cd "Project A&D - DBS Group 34"
.\.venv\Scripts\Activate.ps1

# Of als je in de root directory bent:
cd "c:\UGent\Project A&D, DBS\web-application-2025-group-34-1"
.\.venv\Scripts\Activate.ps1
```

### Stap 3: Maak een Alembic migratie voor de nieuwe kolommen
```bash
# Navigeer naar de project directory
cd "Project A&D - DBS Group 34"

# Maak een nieuwe migratie
flask db migrate -m "add_analist_start_date_and_created_at_to_members"

# Dit maakt een nieuwe migratie file in migrations/versions/
```

### Stap 4: Pas de migratie aan (indien nodig)
- Open de nieuwe migratie file in `migrations/versions/`
- Controleer of `analist_start_date` en `created_at` kolommen correct worden toegevoegd
- Als de kolommen al bestaan, verwijder ze uit de migratie of maak ze nullable

### Stap 5: Voer de Alembic migratie uit
```bash
# Voer de migratie uit
flask db upgrade
```

### Stap 6: Pas het migratie script aan (BELANGRIJK!)
Open `migrate_to_unified_member.py` en pas aan:
- **Sector mapping** (regel ~120): Map je sector namen naar nummers (1-4)
- **Functie mapping** (regel ~60): Map je voting_right waarden naar functie codes (1-6)
- **Analist nummering**: Bepaal hoe analisten genummerd worden binnen een sector

### Stap 7: Voer het migratie script uit
```bash
# Zorg dat je in de juiste directory bent
cd "Project A&D - DBS Group 34"

# Voer het script uit
python migrate_to_unified_member.py
```

### Stap 8: Controleer de migratie
```bash
# Start de Flask app en test
python run.py

# Of via Flask CLI:
flask run
```

### Stap 9: Test de functionaliteit
1. Log in met een bestaand account
2. Ga naar `/deelnemers` en controleer of alle rollen correct worden getoond
3. Test of ID's correct worden weergegeven (6 cijfers)
4. Controleer of rollen correct worden gedetecteerd

### Stap 10: (Optioneel) Verwijder oude tabellen
**ALLEEN DOEN NA VERIFICATIE DAT ALLES WERKT!**

```sql
-- Via psql of je database client:
DROP TABLE IF EXISTS board_members;
DROP TABLE IF EXISTS Analist;
```

Of via Python:
```python
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    db.session.execute(text("DROP TABLE IF EXISTS board_members"))
    db.session.execute(text("DROP TABLE IF EXISTS Analist"))
    db.session.commit()
    print("Oude tabellen verwijderd")
```

## Troubleshooting

### Als de migratie faalt:
1. **Herstel van backup:**
   ```bash
   psql je_database_naam < backup_voor_migratie.sql
   ```

2. **Check database connectie:**
   ```bash
   # Test of je database bereikbaar is
   flask db current
   ```

3. **Check voor conflicterende IDs:**
   ```python
   from app import create_app, db
   from app.models import Member
   
   app = create_app()
   with app.app_context():
       # Check voor duplicate IDs
       members = db.session.query(Member).all()
       ids = [m.member_id for m in members]
       duplicates = [id for id in ids if ids.count(id) > 1]
       if duplicates:
           print(f"Waarschuwing: Duplicate IDs gevonden: {duplicates}")
   ```

### Als nieuwe gebruikers aanmaken faalt:
- Zorg dat je de ID-generatie functies gebruikt
- Check of het ID al bestaat in de database
- Gebruik `get_next_available_id()` voor automatische nummering

## Handige Commands

### Check huidige database status:
```bash
flask db current
flask db history
```

### Maak een nieuwe gebruiker met ID-generatie:
```python
from app import create_app, db
from app.models import Member, generate_lid_id

app = create_app()
with app.app_context():
    # Voor een lid:
    new_id = generate_lid_id(member_number=1, year=2025)
    member = Member(
        member_id=new_id,
        member_name="Test User",
        email="test@example.com"
    )
    member.set_password("password123")
    db.session.add(member)
    db.session.commit()
    print(f"Gebruiker aangemaakt met ID: {new_id}")
```

