from database import SessionLocal
from models import Tender
from collections import Counter

db = SessionLocal()
tenders = db.query(Tender).all()
province_counts = Counter(t.province for t in tenders if t.province)
null_count = sum(1 for t in tenders if t.province is None)

print("Province distribution:")
for prov, count in province_counts.most_common():
    print(f"  {prov}: {count}")
print(f"  NULL: {null_count}")
print(f"Total: {len(tenders)}")
db.close()
