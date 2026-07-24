import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import inspect, text
from app.core.database import engine
from app.models import *  # noqa
from app.models.base import Base

def run_audit():
    print("=" * 80)
    print("LAUNDRA SAAS DATABASE SCHEMA & INTEGRITY AUDIT REPORT")
    print("=" * 80)
    
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return

    print(f"\n[INFO] Total Tables Found in Database: {len(existing_tables)}")
    print(f"[INFO] Total Models Defined in Codebase: {len(Base.metadata.tables)}\n")
    
    missing_tables = []
    missing_columns = {}
    table_stats = []

    with engine.connect() as conn:
        for table_name, table_obj in Base.metadata.tables.items():
            if table_name not in existing_tables:
                missing_tables.append(table_name)
                continue
            
            db_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
            model_columns = {col.name: col for col in table_obj.columns}
            
            missing_cols = []
            for col_name in model_columns:
                if col_name not in db_columns:
                    missing_cols.append(col_name)
            
            if missing_cols:
                missing_columns[table_name] = missing_cols
            
            # Count rows
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                row_count = result.scalar()
            except Exception:
                row_count = "N/A"
                
            status_str = "OK" if not missing_cols else f"MISSING {len(missing_cols)} COLS"
            table_stats.append({
                "table": table_name,
                "rows": row_count,
                "columns_count": len(db_columns),
                "status": status_str
            })

    # Summary Display
    print("-" * 80)
    print(f"{'TABLE NAME':<35} | {'ROWS':<10} | {'COLUMNS':<10} | {'STATUS'}")
    print("-" * 80)
    for stat in sorted(table_stats, key=lambda x: x["table"]):
        print(f"{stat['table']:<35} | {str(stat['rows']):<10} | {str(stat['columns_count']):<10} | {stat['status']}")
    print("-" * 80)

    # Missing Tables Report
    if missing_tables:
        print("\n[WARNING] MISSING TABLES IN DATABASE:")
        for t in missing_tables:
            print(f"  - Table: '{t}' does not exist in DB!")
    else:
        print("\n[SUCCESS] ALL MODELS HAVE CORRESPONDING TABLES IN DATABASE.")

    # Missing Columns Report
    if missing_columns:
        print("\n[WARNING] MISSING COLUMNS IN EXISTING TABLES:")
        for tbl, cols in missing_columns.items():
            print(f"  - Table '{tbl}' is missing column(s): {', '.join(cols)}")
    else:
        print("[SUCCESS] ALL COLUMNS SPECIFIED IN CODEBASE EXIST IN DATABASE.")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    run_audit()
