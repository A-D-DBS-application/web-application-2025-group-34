# Stappenplan - Wat moet je uitvoeren?

## ⚠️ BELANGRIJK: Volg deze volgorde!

### Stap 1: Database Backup (EERST!)
```bash
pg_dump je_database_naam > backup_voor_migratie.sql
```

### Stap 2: Activeer Virtual Environment
```powershell
cd "c:\UGent\Project A&D, DBS\web-application-2025-group-34-1\Project A&D - DBS Group 34"
.\.venv\Scripts\Activate.ps1
```

### Stap 3: Database Schema Migratie (Alembic)
**Dit wijzigt de database structuur (kolommen)**

```bash
# De migratie is al aangemaakt, voer hem nu uit:
flask db upgrade
```

**Wat dit doet:**
- Converteert `join_date` van TIMESTAMP naar INTEGER (jaar)
- Verwijdert `analist_start_date` kolom

### Stap 4: Data Migratie (Optioneel - alleen als je oude data hebt)
**Dit migreert data van oude tabellen naar nieuwe structuur**

```bash
# Pas eerst het script aan met jouw sector/functie mappings
# Open: migrate_to_unified_member.py
# Pas aan: sector mapping, functie mapping

# Voer dan uit:
python migrate_to_unified_member.py
```

**Wanneer nodig:**
- Als je data hebt in `board_members` tabel → migreer naar `members`
- Als je data hebt in `Analist` tabel → migreer naar `members`
- Als je GEEN oude data hebt → SKIP deze stap

### Stap 5: Wachtwoorden Instellen
**Dit zet wachtwoorden in de database**

```bash
# Het script is al ingesteld op jouw CSV bestand
python set_passwords.py
```

**Of met custom pad:**
```bash
python set_passwords.py "c:\Users\jibbe\Downloads\passwords.csv"
```

**Wat dit doet:**
- Leest passwords.csv
- Hasht wachtwoorden
- Zet ze in de `password_hash` kolom van members

### Stap 6: Testen
```bash
# Start de applicatie
python run.py

# Of via Flask:
flask run
```

**Test:**
1. Log in met een account uit je CSV
2. Ga naar `/deelnemers` en controleer of alles correct wordt getoond
3. Controleer of ID's correct zijn (6 cijfers)
4. Controleer of rollen correct worden gedetecteerd

---

## Samenvatting - Wat moet je RUNNEN:

### ✅ VERPLICHT:
1. `flask db upgrade` - Database schema migratie
2. `python set_passwords.py` - Wachtwoorden instellen

### ⚠️ OPTIONEEL (alleen als je oude data hebt):
3. `python migrate_to_unified_member.py` - Data migratie

---

## Troubleshooting

### Als `flask db upgrade` faalt:
- Check of je database bereikbaar is
- Check of er geen actieve connecties zijn
- Probeer opnieuw

### Als `set_passwords.py` faalt:
- Check of het CSV pad correct is
- Check of de Members al bestaan in de database
- Check of de CSV format correct is (semicolon delimiter)

### Als Members niet bestaan:
- Maak ze eerst aan via de applicatie
- Of gebruik het migratie script om ze aan te maken
- Of maak ze handmatig aan via SQL/Python

