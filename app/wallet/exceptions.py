class WalletException(Exception):
    """Base exception for Google Wallet operations"""
    pass

class WalletAuthenticationError(WalletException):
    """Raised when authentication with Google Wallet API fails"""
    pass

class WalletClassError(WalletException):
    """Raised when creating or fetching a Google Wallet Generic Class fails"""
    pass

class WalletObjectError(WalletException):
    """Raised when creating or fetching a Google Wallet Generic Object fails"""
    pass

class WalletJWTError(WalletException):
    """Raised when generating or signing a Google Wallet JWT fails"""
    pass
