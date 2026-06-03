# CRUMB Platform — buildcrumb.com

The social platform for the CRUMB ecosystem.
Every device gets a number. Every builder gets a profile.

## Setup (5 minutes)

### 1. Install dependencies
```bash
pip install flask flask-sqlalchemy flask-login werkzeug
```

### 2. Generate access codes
```bash
python3 generate_codes.py --print
```
This creates `crumb.db` with 1000 unique codes and writes them to `access_codes.txt`.
Print, cut, and include one card per device shipped.

### 3. Run locally
```bash
python3 app.py
```
Visit http://localhost:5000

### 4. Deploy to Render (free)
1. Push to GitHub
2. Go to render.com → New Web Service
3. Connect repo → Runtime: Python 3 → Build: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add env var: `SECRET_KEY` → any long random string
6. Deploy

### 5. Connect domain
In Render settings → Custom Domains → add buildcrumb.com
Then in your DNS provider, add the CNAME record Render provides.

## File structure
```
buildcrumb/
  app.py              Flask application
  generate_codes.py   Run once to seed access codes
  requirements.txt    Dependencies
  templates/
    base.html         Shared layout
    index.html        Landing page
    register.html     Registration
    login.html        Sign in
    profile.html      User profile
    profile_edit.html Edit profile
    discover.html     Browse all builders
    404.html          Error page
  static/
    style.css         Dark fantasy styles
    particles.js      Floating particle animation
```

## The access code system
- Each CRUMB device ships with a physical card containing one unique code
- Format: `CRUMB-0001-XXXXXX`
- Codes are single-use — one device, one registration
- First 100 registrations are Founding Members (permanent badge)
- CRUMB numbers are sequential and permanent

## Adding new device types
In `templates/profile.html`, the add-device form has a select dropdown.
Add new options there as new devices are built.

## Built by Wyeth Anzilotti
Open source. Sacred utility. For everyone.
github.com/wyetherp/crumb_main
