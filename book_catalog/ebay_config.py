"""eBay API configuration."""

import os
from typing import Optional


class eBayConfig:
    """Configuration for eBay API credentials."""
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        cert_id: Optional[str] = None,
        dev_id: Optional[str] = None,
        sandbox: bool = True
    ):
        """
        Initialize eBay configuration.
        
        Args:
            app_id: App ID (Client ID). If None, reads from EBAY_APP_ID env var.
            cert_id: Cert ID (Client Secret). If None, reads from EBAY_CERT_ID env var.
            dev_id: Dev ID (Developer ID). If None, reads from EBAY_DEV_ID env var.
            sandbox: Whether to use Sandbox (True) or Production (False)
        """
        self.app_id = app_id or os.getenv("EBAY_APP_ID")
        self.cert_id = cert_id or os.getenv("EBAY_CERT_ID")
        self.dev_id = dev_id or os.getenv("EBAY_DEV_ID")
        self.sandbox = sandbox
        
        if not self.app_id or not self.cert_id or not self.dev_id:
            raise ValueError(
                "eBay credentials not provided. Set EBAY_APP_ID, EBAY_CERT_ID, and EBAY_DEV_ID "
                "environment variables, or pass them directly to eBayConfig."
            )
    
    @classmethod
    def from_sandbox_credentials(
        cls,
        app_id: str,
        cert_id: str,
        dev_id: str
    ) -> "eBayConfig":
        """Create config from Sandbox credentials."""
        return cls(app_id=app_id, cert_id=cert_id, dev_id=dev_id, sandbox=True)
    
    @classmethod
    def from_production_credentials(
        cls,
        app_id: str,
        cert_id: str,
        dev_id: str
    ) -> "eBayConfig":
        """Create config from Production credentials."""
        return cls(app_id=app_id, cert_id=cert_id, dev_id=dev_id, sandbox=False)

