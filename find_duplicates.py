import sqlite3
import pandas as pd
import os

def find_duplicates():
    print("🔍 Analyzing database for duplicates...")
    
    conn = sqlite3.connect('dismissed_jobs.db')
    
    query = '''
    SELECT 
        title, 
        company, 
        COUNT(*) as count, 
        GROUP_CONCAT(job_id) as ids
    FROM dismissed_jobs 
    GROUP BY title, company 
    HAVING count > 1 
    ORDER BY count DESC
    '''
    
    try:
        df = pd.read_sql_query(query, conn)
        
        if not df.empty:
            output_file = 'duplicates.csv'
            df.to_csv(output_file, index=False)
            print(f"✅ Found {len(df)} groups of duplicates.")
            print(f"📄 Saved report to {output_file}")
            print("\nTop 5 Duplicates:")
            print(df.head(5))
        else:
            print("✅ No duplicates found in database.")
            
    except Exception as e:
        print(f"❌ Error analysis: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    find_duplicates()
