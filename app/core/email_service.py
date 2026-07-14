import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from app.models.platform_settings import PlatformSettings


def get_platform_smtp_settings(db: Session) -> dict:
    """Fetch SMTP settings from the platform_settings table (Super Admin config)."""
    settings = db.query(PlatformSettings).first()
    if not settings:
        return None
    
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        return None
    
    return {
        "host": settings.smtp_host,
        "port": int(settings.smtp_port) if settings.smtp_port else 587,
        "username": settings.smtp_username,
        "password": settings.smtp_password,
        "platform_name": settings.platform_name or "Laundry SaaS"
    }


def send_otp_email(db: Session, to_email: str, otp: str) -> bool:
    """
    Send a real OTP email using the Super Admin's platform SMTP settings.
    
    All OTP emails across all companies are sent from the platform's
    centralized SMTP configuration set by the Super Admin.
    
    Returns True if email sent successfully, False otherwise.
    """
    smtp_config = get_platform_smtp_settings(db)
    
    if not smtp_config:
        print(f"[EMAIL WARNING] Platform SMTP not configured. OTP for {to_email}: {otp}")
        return False
    
    platform_name = smtp_config["platform_name"]
    from_email = smtp_config["username"]
    
    # Build a nice HTML email
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #2c3e50; text-align: center; margin-bottom: 10px;">
                🔐 Email Verification
            </h2>
            <p style="color: #555; text-align: center; font-size: 15px;">
                Your One-Time Password (OTP) from <strong>{platform_name}</strong> is:
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    padding: 15px 30px;
                    border-radius: 10px;
                ">{otp}</span>
            </div>
            <p style="color: #888; text-align: center; font-size: 13px;">
                This OTP is valid for <strong>10 minutes</strong>. Do not share it with anyone.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
            <p style="color: #aaa; text-align: center; font-size: 12px;">
                If you did not request this, please ignore this email.<br>
                &copy; {platform_name}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"Your OTP from {platform_name} is: {otp}. Valid for 10 minutes."
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔐 Your OTP Code - {platform_name}"
    msg["From"] = f"{platform_name} <{from_email}>"
    msg["To"] = to_email
    
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    
    try:
        server = smtplib.SMTP(smtp_config["host"], smtp_config["port"])
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_config["username"], smtp_config["password"])
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL] OTP email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send OTP to {to_email}: {str(e)}")
        return False


def send_approval_email(db: Session, to_email: str, company_name: str) -> bool:
    """Send an account approval notification email."""
    smtp_config = get_platform_smtp_settings(db)
    if not smtp_config:
        print(f"[EMAIL WARNING] Platform SMTP not configured. Approval sent to {to_email}")
        return False
        
    platform_name = smtp_config["platform_name"]
    from_email = smtp_config["username"]
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #2ecc71; text-align: center; margin-bottom: 10px;">
                🎉 Account Approved!
            </h2>
            <p style="color: #555; text-align: center; font-size: 15px;">
                Congratulations! Your Delivery boy account has been approved by the admin of <strong>{company_name}</strong>.
            </p>
            <p style="color: #555; text-align: center; font-size: 15px;">
                You can now log in to the delivery application using your registered email and password.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
            <p style="color: #aaa; text-align: center; font-size: 12px;">
                &copy; {platform_name}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"Congratulations! Your account has been approved by the admin of {company_name}. You can now log in."
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎉 Account Approved - {platform_name}"
    msg["From"] = f"{platform_name} <{from_email}>"
    msg["To"] = to_email
    
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    
    try:
        server = smtplib.SMTP(smtp_config["host"], smtp_config["port"])
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_config["username"], smtp_config["password"])
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL] Approval email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send approval email to {to_email}: {str(e)}")
        return False


def send_rejection_email(db: Session, to_email: str, company_name: str) -> bool:
    """Send an account rejection notification email."""
    smtp_config = get_platform_smtp_settings(db)
    if not smtp_config:
        print(f"[EMAIL WARNING] Platform SMTP not configured. Rejection sent to {to_email}")
        return False
        
    platform_name = smtp_config["platform_name"]
    from_email = smtp_config["username"]
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #e74c3c; text-align: center; margin-bottom: 10px;">
                Account Application Update
            </h2>
            <p style="color: #555; text-align: center; font-size: 15px;">
                We regret to inform you that your Delivery Boy application for <strong>{company_name}</strong> has been rejected by the admin.
            </p>
            <p style="color: #555; text-align: center; font-size: 15px;">
                If you have any questions, please contact the company directly.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
            <p style="color: #aaa; text-align: center; font-size: 12px;">
                &copy; {platform_name}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"We regret to inform you that your application for {company_name} has been rejected by the admin."
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Account Application Update - {platform_name}"
    msg["From"] = f"{platform_name} <{from_email}>"
    msg["To"] = to_email
    
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    
    try:
        server = smtplib.SMTP(smtp_config["host"], smtp_config["port"])
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_config["username"], smtp_config["password"])
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL] Rejection email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send rejection email to {to_email}: {str(e)}")
        return False

def send_order_otp_email(db: Session, to_email: str, otp: str, action: str, company_name: str) -> bool:
    """Send an OTP email to the customer for order pickup or delivery verification."""
    smtp_config = get_platform_smtp_settings(db)
    if not smtp_config:
        print(f"[EMAIL WARNING] Platform SMTP not configured. Order OTP sent to {to_email}: {otp}")
        return False
        
    platform_name = smtp_config["platform_name"]
    from_email = smtp_config["username"]
    action_text = "Pickup" if action == "pickup" else "Delivery"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #2c3e50; text-align: center; margin-bottom: 10px;">
                📦 Order {action_text} Verification
            </h2>
            <p style="color: #555; text-align: center; font-size: 15px;">
                Your delivery agent from <strong>{company_name}</strong> is ready to complete the {action_text.lower()} of your order.
            </p>
            <p style="color: #555; text-align: center; font-size: 15px;">
                Please provide the following OTP to the delivery agent to verify and complete the {action_text.lower()}:
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="
                    display: inline-block;
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    padding: 15px 30px;
                    border-radius: 10px;
                ">{otp}</span>
            </div>
            <p style="color: #888; text-align: center; font-size: 13px;">
                This OTP is valid for <strong>15 minutes</strong>.
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
            <p style="color: #aaa; text-align: center; font-size: 12px;">
                &copy; {platform_name}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"Your OTP for order {action_text.lower()} from {company_name} is: {otp}. Valid for 15 minutes."
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📦 Your Order {action_text} OTP - {company_name}"
    msg["From"] = f"{platform_name} <{from_email}>"
    msg["To"] = to_email
    
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    
    try:
        server = smtplib.SMTP(smtp_config["host"], smtp_config["port"])
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_config["username"], smtp_config["password"])
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL] Order {action_text} OTP sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send order {action_text} OTP to {to_email}: {str(e)}")
        return False


