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
        pkg_name = package.package.name if package.package else "Prepaid Package"
        validity = f"{package.activation_date.strftime('%d %b %Y')} - {package.expiry_date.strftime('%d %b %Y')}" if package.activation_date and package.expiry_date else "N/A"
        
        msg = f"""
------------------------------------------------
ABC Laundry

Hello {customer_name} 👋
Your prepaid package has been successfully activated.

Package : {pkg_name}
Package Value : ₹{float(package.package_value):.2f}
Current Balance : ₹{float(package.current_balance):.2f}

Validity : {validity}
Your Digital Membership Card is ready.

[ QR Preview ]
██████████

Buttons
[ Add to Google Wallet ] -> {package.google_wallet_url or ''}
OR
[ Add to Apple Wallet ] -> {package.apple_wallet_url or ''}
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
