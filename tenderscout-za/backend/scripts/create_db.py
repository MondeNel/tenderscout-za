#!/usr/bin/env python
"""
Create database tables with the updated schema.
Run: python scripts/create_db.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine
import models

print("🔨 Creating database tables...")
models.Base.metadata.create_all(bind=engine)
print("✅ Database created successfully with all tables!")
print("")
print("Tables created:")
for table in models.Base.metadata.sorted_tables:
    print(f"  - {table.name}")