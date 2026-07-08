from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from uuid import uuid4, UUID
from pydantic import BaseModel
from fpdf import FPDF
import random

from app.schemas.invoice import InvoiceOut

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.invoice import Invoice
from app.models.company import Company
from app.models.customer import Customer
from app.models.order_item import OrderItem
from app.models.service import Service
from app.core.tenant import get_current_tenant_id

router = APIRouter()

class InvoiceGenerateRequest(BaseModel):
    order_id: UUID

@router.post("/generate", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def generate_invoice(
    payload: InvoiceGenerateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = current_admin.tenant_id
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.tenant_id == tenant_id
    ).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
        
    existing = db.query(Invoice).filter(
        Invoice.order_id == order.id,
        Invoice.tenant_id == tenant_id
    ).first()
    if existing:
        return existing
        
    prefix = "INV-"
    
    invoice_number = f"{prefix}{order.order_number[-8:]}-{random.randint(100, 999)}"
    
    invoice = Invoice(
        id=uuid4(),
        tenant_id=tenant_id,
        order_id=order.id,
        invoice_number=invoice_number,
        amount=order.total_amount,
        status="PAID" if order.payment_status == "PAID" else "UNPAID"
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    # Audit log
    from app.models.audit_log import AuditLog
    audit = AuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_admin.id,
        action=f"Generated invoice {invoice_number} for Order {order.order_number}",
        module="Invoice"
    )
    db.add(audit)
    db.commit()
    
    return invoice

@router.get("/{id}", response_model=InvoiceOut)
def get_invoice(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tenant_id = current_user.tenant_id
    invoice = db.query(Invoice).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    return invoice

@router.get("/download/{id}")
def download_invoice(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tenant_id = current_user.tenant_id
    invoice = db.query(Invoice).filter(
        Invoice.id == id,
        Invoice.tenant_id == tenant_id
    ).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
        
    order = db.query(Order).filter(
        Order.id == invoice.order_id,
        Order.tenant_id == tenant_id
    ).first()
    
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    company = db.query(Company).filter(Company.id == tenant_id).first()
    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    pdf = FPDF()
    pdf.add_page()
    
    # Header: Company Name & Address
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(60, 80, 120)
    pdf.set_fill_color(240, 245, 255)
    company_name = company.name if company else "YOUR COMPANY NAME"
    pdf.cell(0, 8, company_name, ln=True, align="C", fill=True)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    company_contact = []
    if company and company.phone: company_contact.append(company.phone)
    if company and company.email: company_contact.append(company.email)
    contact_str = ", ".join(company_contact) if company_contact else "Street Address, City, State, Zip Code"
    pdf.cell(0, 6, contact_str, ln=True, align="C", fill=True)
    
    pdf.ln(10)
    
    # "INVOICE" Title with lines
    pdf.set_font("helvetica", "B", 32)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 15, "INVOICE", ln=True, align="C")
    y = pdf.get_y() - 7
    pdf.set_draw_color(200, 180, 160)
    pdf.set_line_width(1.5)
    pdf.line(10, y, 70, y)
    pdf.line(140, y, 200, y)
    
    pdf.ln(15)
    
    # Bill To & Dates
    y_start = pdf.get_y()
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(90, 5, "BILL TO:", ln=True)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(60, 80, 120)
    pdf.set_fill_color(240, 245, 255)
    customer_name = customer.name if (customer and customer.name) else "CUSTOMER NAME"
    pdf.cell(90, 6, customer_name, ln=True, fill=True)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    customer_address = customer.address if (customer and customer.address) else "Street Address, City,\nState, Zip Code"
    pdf.multi_cell(90, 5, customer_address, fill=True)
    
    # Right Side (Invoice details)
    pdf.set_xy(120, y_start)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(30, 6, "Invoice #:", align="R")
    pdf.cell(40, 6, invoice.invoice_number, fill=True, align="L", ln=True)
    
    pdf.set_x(120)
    pdf.cell(30, 6, "Issue Date:", align="R")
    issue_date = invoice.created_at.strftime("%Y-%m-%d") if invoice.created_at else "N/A"
    pdf.cell(40, 6, issue_date, fill=True, align="L", ln=True)
    
    pdf.set_x(120)
    pdf.cell(30, 6, "Due Date:", align="R")
    pdf.cell(40, 6, issue_date, fill=True, align="L", ln=True)
    
    pdf.ln(15)
    
    # Table Header
    pdf.set_y(max(pdf.get_y(), y_start + 30))
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(90, 8, "Description", border=0)
    pdf.cell(30, 8, "Price", border=0)
    pdf.cell(30, 8, "QTY", border=0)
    pdf.cell(30, 8, "Total", border=0, ln=True)
    
    # Line under header
    pdf.set_line_width(0.5)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    
    # Table Rows
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    
    subtotal = 0.0
    for item in items:
        service = db.query(Service).filter(Service.id == item.service_id).first()
        desc = service.name if service else "Service"
        total = float(item.price) * item.quantity
        subtotal += total
        pdf.cell(90, 8, desc, fill=True)
        pdf.cell(30, 8, f"{float(item.price):.2f}", fill=True)
        pdf.cell(30, 8, f"{item.quantity}", fill=True)
        pdf.cell(30, 8, f"{total:.2f}", fill=True, ln=True)
        pdf.ln(2)
        
    # Line under items
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # Totals
    y_totals = pdf.get_y()
    pdf.set_xy(120, y_totals)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(40, 8, "Subtotal", align="L")
    pdf.cell(40, 8, f"{subtotal:.2f}", fill=True, align="L", ln=True)
    
    pdf.set_x(120)
    pdf.cell(40, 8, "Discount", align="L")
    discount = float(order.discount) if order and order.discount else 0.0
    pdf.cell(40, 8, f"{discount:.2f}", fill=True, align="L", ln=True)
    
    pdf.set_line_width(0.5)
    pdf.line(120, pdf.get_y(), 200, pdf.get_y())
    
    pdf.set_x(120)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(40, 8, "Total Due", align="L")
    pdf.cell(40, 8, f"{float(invoice.amount):.2f}", fill=True, align="L", ln=True)
    
    # Payment Terms & Notes
    pdf.set_xy(10, y_totals)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(90, 6, "Payment Terms:", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(90, 6, f"Status: {invoice.status}\nPlease pay promptly.", fill=True)
    
    pdf.ln(5)
    pdf.set_x(10)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(90, 6, "Notes:", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(90, 6, "Thank you for your business!", fill=True)
    
    pdf_bytes = bytes(pdf.output())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice.invoice_number}.pdf"}
    )
