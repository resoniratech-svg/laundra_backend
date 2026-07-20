import uuid
import logging
from app.models.customer_package import CustomerPackage

logger = logging.getLogger(__name__)

class WalletService:
    @staticmethod
    def generate_apple_wallet_link(package: CustomerPackage) -> str:
        """
        Mock implementation. In production, this would use a `.pkpass` generator
        or a PassKit-like API and return a secure link.
        """
        mock_id = str(uuid.uuid4())[:8]
        return f"https://wallet.apple.com/add/pass/mock_{mock_id}"

    @staticmethod
    def generate_google_wallet_link(package: CustomerPackage) -> str:
        """
        Mock implementation. In production, this would call the Google Wallet API
        to generate an object and return a signed JWT link.
        """
        mock_id = str(uuid.uuid4())[:8]
        return f"https://pay.google.com/gp/v/save/mock_{mock_id}"

    @staticmethod
    def update_pass_color(package: CustomerPackage) -> str:
        """
        Updates the wallet pass color based on the current balance or status.
        Gold = Full / Active
        Grey = In Use (balance deducted)
        Orange = Low Balance (< 10%)
        White = Completed / Empty
        """
        if package.current_balance <= 0 or package.status in ['COMPLETED', 'FULLY_UTILIZED', 'EXPIRED']:
            return "WHITE"
        
        if package.package_value and package.package_value > 0:
            ratio = float(package.current_balance) / float(package.package_value)
            if ratio < 0.15:
                return "ORANGE"
            elif ratio < 1.0:
                return "GREY"
                
        return "GOLD"
