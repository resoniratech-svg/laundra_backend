from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.review import Review

router = APIRouter()

class ReviewOut(BaseModel):
    id: UUID
    customer_id: UUID
    order_id: Optional[UUID] = None
    rating: int
    comment: Optional[str] = None
    reply: Optional[str] = None
    is_hidden: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ReplyPayload(BaseModel):
    reply: str

class HidePayload(BaseModel):
    is_hidden: bool

@router.get("", response_model=List[ReviewOut])
def list_reviews(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Company Admin views all reviews for their company.
    """
    return db.query(Review).filter(
        Review.tenant_id == current_admin.tenant_id
    ).order_by(desc(Review.created_at)).all()

@router.post("/{review_id}/reply", response_model=ReviewOut)
def reply_to_review(
    review_id: UUID,
    payload: ReplyPayload,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Company Admin replies to a customer review.
    """
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.tenant_id == current_admin.tenant_id
    ).first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
        
    review.reply = payload.reply
    db.commit()
    db.refresh(review)
    return review

@router.patch("/{review_id}/hide", response_model=ReviewOut)
def toggle_review_visibility(
    review_id: UUID,
    payload: HidePayload,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Company Admin toggles the visibility of a review.
    """
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.tenant_id == current_admin.tenant_id
    ).first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
        
    review.is_hidden = payload.is_hidden
    db.commit()
    db.refresh(review)
    return review
