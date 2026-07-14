from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_customer
from app.models.user import User
from app.models.customer import Customer
from app.models.review import Review
from uuid import uuid4

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
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None

    class Config:
        from_attributes = True

class ReplyPayload(BaseModel):
    reply: str

class HidePayload(BaseModel):
    is_hidden: bool

class ReviewCreate(BaseModel):
    rating: int
    comment: Optional[str] = None
    order_id: Optional[UUID] = None

@router.get("", response_model=List[ReviewOut])
def list_reviews(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Company Admin views all reviews for their company.
    """
    results = db.query(Review, Customer).outerjoin(
        Customer, Review.customer_id == Customer.id
    ).filter(
        Review.tenant_id == current_admin.tenant_id
    ).order_by(desc(Review.created_at)).all()
    
    out_list = []
    for review, customer in results:
        out_list.append(ReviewOut(
            id=review.id,
            customer_id=review.customer_id,
            order_id=review.order_id,
            rating=review.rating,
            comment=review.comment,
            reply=review.reply,
            is_hidden=review.is_hidden,
            created_at=review.created_at,
            customer_name=customer.name if customer else None,
            customer_email=customer.email if customer else None,
            customer_phone=customer.phone if customer else None,
            customer_address=customer.address if customer else None
        ))
    return out_list

@router.get("/me", response_model=List[ReviewOut])
def list_my_reviews(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    Customer views all their own reviews.
    """
    reviews = db.query(Review).filter(
        Review.customer_id == current_customer.id
    ).order_by(desc(Review.created_at)).all()
    
    out_list = []
    for review in reviews:
        out_list.append(ReviewOut(
            id=review.id,
            customer_id=review.customer_id,
            order_id=review.order_id,
            rating=review.rating,
            comment=review.comment,
            reply=review.reply,
            is_hidden=review.is_hidden,
            created_at=review.created_at,
            customer_name=current_customer.name,
            customer_email=current_customer.email,
            customer_phone=current_customer.phone,
            customer_address=current_customer.address
        ))
    return out_list

@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    Customer submits a review.
    """
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
    review = Review(
        id=uuid4(),
        tenant_id=current_customer.tenant_id,
        customer_id=current_customer.id,
        order_id=payload.order_id,
        rating=payload.rating,
        comment=payload.comment
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return ReviewOut(
        id=review.id,
        customer_id=review.customer_id,
        order_id=review.order_id,
        rating=review.rating,
        comment=review.comment,
        reply=review.reply,
        is_hidden=review.is_hidden,
        created_at=review.created_at,
        customer_name=current_customer.name,
        customer_email=current_customer.email,
        customer_phone=current_customer.phone,
        customer_address=current_customer.address
    )

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
