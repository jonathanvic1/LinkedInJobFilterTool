from database import db

def check_db_blocklist(name):
    print(f"\n🔍 Checking Supabase Blocklist: {name}...")
    
    items = db.get_blocklist(name)
    
    seen = set()
    duplicates = []
    whitespace_issues = []
    
    for i, original in enumerate(items):
        stripped = original.strip()
            
        # Check Whitespace
        if original != stripped:
            whitespace_issues.append((i + 1, original))
            
        # Check Duplicates (case-insensitive)
        lower = stripped.lower()
        if lower in seen:
            duplicates.append((i + 1, stripped))
        else:
            seen.add(lower)
            
    # Report
    print(f"   📄 Total Items: {len(items)}")
    
    if duplicates:
        print(f"   ⚠️  Found {len(duplicates)} duplicates:")
        for ln, text in duplicates:
            print(f"      - Item {ln}: '{text}'")
    else:
        print("   ✅ No duplicates found.")
        
    if whitespace_issues:
        print(f"   ⚠️  Found {len(whitespace_issues)} items with leading/trailing whitespace:")
        for ln, text in whitespace_issues:
            print(f"      - Item {ln}: '{text}'")
    else:
        print("   ✅ No whitespace issues found.")

if __name__ == "__main__":
    check_db_blocklist('job_title')
    check_db_blocklist('company_linkedin')
