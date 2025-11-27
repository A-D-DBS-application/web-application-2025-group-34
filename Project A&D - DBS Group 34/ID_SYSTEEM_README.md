# ID-Systeem Documentatie

## Overzicht

Alle gebruikers (board, analisten, leden, kapitaalverschaffers, oud-bestuur/analisten) zijn nu samengevoegd in één `Member` tabel. De rol wordt bepaald op basis van het eerste cijfer van het 6-cijferig ID-nummer.

## ID-Structuur (6 cijfers)

```
[ROL][FUNCTIE/SECTOR/NUMMER][JAAR]
 1     2-3                   4-6
```

### Rol-bepaling (eerste cijfer):
- **0** = Board/Bestuur
- **1** = Analist
- **2** = Lid
- **3** = Kapitaalverschaffers
- **4** = Oud-bestuur/oud-analisten

### Laatste 3 cijfers = Jaar:
- 2025 → `025`
- 2024 → `024`
- etc.

## Specifieke formaten per rol:

### Board (0xxyyy):
- Cijfers 2-3 = functie:
  - `001` = Voorzitter
  - `002` = Vice-voorzitter
  - `003` = Portfolio Manager
  - `004` = Fund Administrator
  - `005` = Marketing
  - `006` = Public Relations
- **Voorbeeld**: `001025` = Voorzitter 2025

### Analisten (1xxyyy):
- Cijfer 2 = Sector (1-4)
- Cijfer 3 = Nummer in sector (1-9)
- **Voorbeeld**: `111025` = Sector 1, Analist 1, 2025

### Leden (2xxyyy):
- Cijfers 2-3 = Volgnummer in jaar (00-99)
- Max 100 leden per jaar
- **Voorbeeld**: `201025` = Lid #1 in 2025

### Kapitaalverschaffers (3xxyyy):
- Cijfers 2-3 = Uniek nummer (00-99)
- **Voorbeeld**: `301024` = Kapverschaffer #1, 2024

### Oud-bestuur/analisten (4xxyyy):
- Eerste cijfer wordt 4
- Rest blijft hetzelfde
- **Voorbeeld**: `001025` → `401025` (oud voorzitter)

## Gebruik in Code

### Rol bepalen:
```python
member = db.session.get(Member, member_id)
role = member.get_role()  # 'board', 'analist', 'lid', etc.
```

### Helper methodes:
```python
# Voor board members
function_code = member.get_board_function()  # 1-6
function_name = member.get_board_function_name()  # "Voorzitter", etc.

# Voor analisten
sector = member.get_analist_sector()  # 1-4
analist_num = member.get_analist_number_in_sector()

# Voor leden
member_num = member.get_member_number_in_year()

# Voor alle rollen
year = member.get_year()  # 2025, 2024, etc.
```

### ID genereren:
```python
from app.models import (
    generate_board_member_id,
    generate_analist_id,
    generate_lid_id,
    generate_kapitaalverschaffer_id,
    convert_to_oud_id,
    get_next_available_id
)

# Board member
board_id = generate_board_member_id(function_code=1, year=2025)  # 001025

# Analist
analist_id = generate_analist_id(sector=1, analist_number=1, year=2025)  # 111025

# Lid
lid_id = generate_lid_id(member_number=1, year=2025)  # 201025

# Kapitaalverschaffer
kv_id = generate_kapitaalverschaffer_id(verschaffer_number=1, year=2024)  # 301024

# Oud-bestuur/analist
oud_id = convert_to_oud_id(001025)  # 401025

# Automatisch volgende beschikbare ID
next_id = get_next_available_id('lid', year=2025)
```

### Permission decorators:
```python
from app.routes import role_required, board_required, analist_required

@main.route("/admin-only")
@login_required
@board_required
def admin_page():
    # Alleen board members kunnen hier komen
    pass

@main.route("/analist-only")
@login_required
@analist_required
def analist_page():
    # Alleen analisten kunnen hier komen
    pass

@main.route("/board-or-analist")
@login_required
@role_required('board', 'analist')
def board_or_analist_page():
    # Board members of analisten kunnen hier komen
    pass
```

## Migratie

Zie `migrate_to_unified_member.py` voor het migratie script.

**BELANGRIJK**: Maak altijd een backup van je database voordat je migreert!

## Aandachtspunten

1. **Geen autoincrement meer**: IDs moeten handmatig worden gegenereerd met de helper functies
2. **Unieke IDs**: Zorg dat elk ID uniek is binnen de database
3. **Jaar-afhankelijk**: IDs zijn jaar-afhankelijk, dus hetzelfde lid kan verschillende IDs hebben in verschillende jaren
4. **Oud-bestuur/analisten**: Gebruik `convert_to_oud_id()` om bestaande IDs te converteren naar oud-formaat

