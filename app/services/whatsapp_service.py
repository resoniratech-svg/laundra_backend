import logging
from app.models.customer_package import CustomerPackage
from app.models.user import User
from decimal import Decimal

logger = logging.getLogger(__name__)

class WhatsAppService:
    @staticmethod
    def send_package_activated_message(customer: User, package: CustomerPackage):
        """
        Mocks sending a WhatsApp message via API (e.g. Twilio, Meta API)
        """
        customer_name = customer.name.split(' ')[0] if customer.name else "Customer"
        pkg_name = package.package.name if (hasattr(package, 'package') and package.package) else "Prepaid Package"
        validity = f"{package.activation_date.strftime('%d %b %Y')} - {package.expiry_date.strftime('%d %b %Y')}" if (package.activation_date and package.expiry_date) else "N/A"
        
        from app.core.config import settings
        base_backend = getattr(settings, "BACKEND_BASE_URL", "https://laundry-project-laundry-backend.cocjl5.easypanel.host").rstrip("/")
        
        apple_url = package.apple_wallet_url or ""
        if apple_url and apple_url.startswith("/"):
            apple_url = f"{base_backend}{apple_url}"

        google_url = package.google_wallet_url or ""
        if google_url and google_url.startswith("/"):
            google_url = f"{base_backend}{google_url}"

        apple_link = f"🍎 Add to Apple Wallet:\n{apple_url}" if apple_url else ""
        google_link = f"🤖 Add to Google Wallet:\n{google_url}" if google_url else ""

        wallet_buttons = []
        if apple_link:
            wallet_buttons.append(apple_link.strip())
        if google_link:
            wallet_buttons.append(google_link.strip())

        buttons_str = "\n\n".join(wallet_buttons) if wallet_buttons else "Digital Membership Card Ready"

        msg = f"""
------------------------------------------------
Laundra Laundry

Hello {customer_name} 👋
Your prepaid package has been successfully activated.

Package : {pkg_name}
Package Value : QR {float(package.package_value or 0.0):.2f}
Current Balance : QR {float(package.current_balance or 0.0):.2f}

Validity : {validity}

{buttons_str}
------------------------------------------------
        """
        logger.info(f"WHATSAPP MESSAGE SENT TO {customer.phone}:\n{msg}")

    @staticmethod
    def send_low_balance_alert(customer: User, package: CustomerPackage):
        """
        Mocks sending a low balance alert.
        """
        customer_name = customer.name.split(' ')[0] if customer.name else "Customer"
        pkg_name = package.package.name if package.package else "Prepaid Package"

        msg = f"""
------------------------------------------------
ABC Laundry

Hello {customer_name} ⚠️
Your {pkg_name} is running low!

Current Balance : ₹{float(package.current_balance):.2f}

Please renew soon to continue enjoying our services.
------------------------------------------------
        """
        logger.info(f"WHATSAPP LOW BALANCE ALERT SENT TO {customer.phone}:\n{msg}")
