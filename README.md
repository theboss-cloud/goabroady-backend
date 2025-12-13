# Goabroady Backend

This repository hosts the Flask backend for Goabroady. It wires together SQLAlchemy, Flask-Migrate, JWT authentication, and multiple blueprints for program management, uploads, billing, and other services.

## Getting started
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables as needed (e.g., `SECRET_KEY`, `JWT_SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`). The defaults use a SQLite database under `instance/your_db.sqlite3`.
4. Initialize or upgrade the database schema:
   ```bash
   FLASK_APP=app:create_app flask db upgrade
   ```
5. Run the development server:
   ```bash
   FLASK_APP=app:create_app flask run --reload
   ```

## Related repositories
- Main project repository: https://github.com/theboss-cloud/goabroady
