import pandas as pd
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from decimal import Decimal
import io
from fastapi import UploadFile, HTTPException, status
from app.models.service import Service

class ImportService:
    @staticmethod
    def import_service_catalog(db: Session, tenant_id: UUID, file: UploadFile):
        if not file.filename.endswith(('.xls', '.xlsx')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only Excel files (.xls, .xlsx) are supported."
            )
        
        try:
            contents = file.file.read()
            df = pd.read_excel(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read Excel file: {str(e)}"
            )

        # Clean column names (forward fill Unnamed columns for merged cells)
        cols = list(df.columns)
        for i in range(len(cols)):
            if str(cols[i]).startswith('Unnamed:'):
                cols[i] = cols[i-1]
        df.columns = cols
        df.columns = df.columns.str.strip()

        # Find the 'Item' column (case-insensitive)
        item_col = None
        for col in df.columns:
            if str(col).lower() in ["item", "items", "item name", "item description"]:
                item_col = col
                break

        if not item_col:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The Excel file must contain an 'Item' column. Found columns: {list(df.columns)}"
            )

        categories = {}
        # Check if first row is sub-header (Normal/Express)
        is_two_row_header = False
        if len(df) > 0:
            first_row = df.iloc[0].astype(str).str.lower()
            is_two_row_header = any(x in ['normal', 'express'] for x in first_row)

        for i, col in enumerate(df.columns):
            cat_name = str(col).strip()
            if cat_name == item_col or cat_name.lower() in ["sl no", "sl. no.", "slno", "no."]:
                continue
            
            if is_two_row_header:
                sub_type = str(df.iloc[0, i]).lower().strip()
                if cat_name not in categories:
                    categories[cat_name] = {'normal': None, 'express': None}
                
                if sub_type == 'express':
                    categories[cat_name]['express'] = i
                else:
                    categories[cat_name]['normal'] = i
            else:
                # One row header logic
                if cat_name.endswith(" Express"):
                    real_cat = cat_name[:-8].strip()
                    if real_cat not in categories:
                        categories[real_cat] = {"normal": None, "express": None}
                    categories[real_cat]["express"] = i
                elif cat_name.endswith(" Normal"):
                    real_cat = cat_name[:-7].strip()
                    if real_cat not in categories:
                        categories[real_cat] = {"normal": None, "express": None}
                    categories[real_cat]["normal"] = i
                else:
                    if cat_name not in categories:
                        categories[cat_name] = {"normal": None, "express": None}
                    categories[cat_name]["normal"] = i

        # Process each row
        added_count = 0
        updated_count = 0
        
        # If two-row header, skip the first data row
        start_idx = 1 if is_two_row_header else 0

        for index in range(start_idx, len(df)):
            row = df.iloc[index]
            val = row[item_col]
            if hasattr(val, 'iloc'):
                val = val.iloc[0]
            item_name = str(val).strip()
            if not item_name or item_name == "nan":
                continue

            for cat_name, mapping in categories.items():
                normal_idx = mapping["normal"]
                express_idx = mapping["express"]

                normal_price = None
                express_price = None

                # Extract normal price
                if normal_idx is not None and pd.notna(row.iloc[normal_idx]):
                    try:
                        normal_price = Decimal(str(row.iloc[normal_idx]))
                    except:
                        pass
                
                # Extract express price
                if express_idx is not None and pd.notna(row.iloc[express_idx]):
                    try:
                        express_price = Decimal(str(row.iloc[express_idx]))
                    except:
                        pass

                # If both are null, nothing to do for this category
                if normal_price is None and express_price is None:
                    continue

                # Check if it exists
                existing = db.query(Service).filter(
                    Service.tenant_id == tenant_id,
                    Service.name == item_name,
                    Service.category == cat_name
                ).first()

                if existing:
                    # Overwrite prices if different
                    updated = False
                    if normal_price is not None and existing.price != normal_price:
                        existing.price = normal_price
                        updated = True
                    if express_price is not None and existing.express_price != express_price:
                        existing.express_price = express_price
                        updated = True
                    if updated:
                        updated_count += 1
                else:
                    # Create new
                    # If normal price is None but express exists, we still need a base price. 
                    # Defaulting to 0 if normal is strictly missing but express exists.
                    if normal_price is None:
                        normal_price = Decimal("0.0")

                    new_service = Service(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        name=item_name,
                        category=cat_name,
                        unit="PIECE",
                        price=normal_price,
                        express_price=express_price
                    )
                    db.add(new_service)
                    db.flush()  # Flush so it can be found in subsequent rows of this import
                    added_count += 1

        db.commit()
        return {"message": f"Import complete. Added {added_count} new services, updated {updated_count} existing services."}
