# test_admin.py
import database

print("🔍 Testing analytics...")
data = database.get_analytics()
print(f"✅ analytics = {data}")
print(f"   total: {data.get('total')}")
print(f"   by_role: {data.get('by_role')}")
print(f"   by_lang: {data.get('by_lang')}")
print(f"   by_urgency: {data.get('by_urgency')}")