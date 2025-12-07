import sys
import os
from pathlib import Path

# Voeg de project directory toe aan Python path
project_dir = Path(__file__).parent / "Project A&D - DBS Group 34"
project_dir_str = str(project_dir.resolve())
if project_dir_str not in sys.path:
    sys.path.insert(0, project_dir_str)

# Importeer de app (na het toevoegen aan sys.path)
from app import create_app  # type: ignore

app = create_app()

if __name__ == "__main__":
    app.run()

