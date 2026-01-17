import os

def check_file(filename):
    if not os.path.exists(filename):
        print(f"❌ {filename} not found.")
        return

    print(f"\n🔍 Checking {filename}...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    seen = set()
    duplicates = []
    whitespace_issues = []
    empty_lines = 0
    
    for i, line in enumerate(lines):
        original = line.strip('\n') # Keep other matching whitespace for checking
        stripped = original.strip()
        
        if not stripped:
            empty_lines += 1
            continue
            
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
    print(f"   📄 Total Lines: {len(lines)}")
    print(f"   ⚪ Empty Lines: {empty_lines}")
    
    if duplicates:
        print(f"   ⚠️  Found {len(duplicates)} duplicates:")
        for ln, text in duplicates:
            print(f"      - Line {ln}: '{text}'")
    else:
        print("   ✅ No duplicates found.")
        
    if whitespace_issues:
        print(f"   ⚠️  Found {len(whitespace_issues)} lines with leading/trailing whitespace:")
        for ln, text in whitespace_issues:
            print(f"      - Line {ln}: '{text}'")
    else:
        print("   ✅ No whitespace issues found.")

if __name__ == "__main__":
    check_file('blocklist.txt')
    check_file('blocklist_companies.txt')
