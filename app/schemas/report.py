from pydantic import BaseModel
from datetime import date
from typing import Optional

class DailySalesReportRequest(BaseModel):
    date: date

class DateRangeRequest(BaseModel):
    start_date: date
    end_date: date
