"""
generate_codes.py
Run this ONCE to seed the database with access codes.
Each CRUMB device ships with one card containing one code.

Usage:
    python3 generate_codes.py          # generates 1000 codes
    python3 generate_codes.py --print  # also prints first 20 to console
"""

import sys
import secrets
from app import app, db, AccessCode


def generate_codes(count=1000):
    """Generate unique access codes and write them to the database."""
    with app.app_context():
        db.create_all()

        existing = AccessCode.query.count()
        new_codes = []

        for i in range(count):
            number = str(existing + i + 1).zfill(4)
            # 12 random alphanumeric chars in 3 groups of 4
            # 62^12 = 3.2 sextillion combinations — unguessable
            raw    = secrets.token_urlsafe(16).upper().replace('-','').replace('_','')
            token  = f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"
            code   = f"CRUMB-{number}-{token}"
            new_codes.append(AccessCode(code=code))

        db.session.add_all(new_codes)
        db.session.commit()

        print(f"Generated {count} codes. Database now has {AccessCode.query.count()} total.")

        if '--print' in sys.argv:
            print("\nFirst 20 codes:")
            for ac in AccessCode.query.limit(20).all():
                print(f"  {ac.code}")

        # Also write to a text file for printing on physical cards
        codes = [ac.code for ac in AccessCode.query.filter_by(used=False).all()]
        with open('access_codes.txt', 'w') as f:
            for code in codes:
                f.write(code + '\n')
        print(f"\nAll unused codes written to access_codes.txt")
        print("Print this file and cut into cards. One per device.")


if __name__ == '__main__':
    generate_codes()
