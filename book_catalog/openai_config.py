"""OpenAI API configuration."""

import os
from typing import Optional


class OpenAIConfig:
    """Configuration for OpenAI API credentials."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI configuration.
        
        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var or openai_credentials.py
        """
        if api_key:
            self.api_key = api_key
        else:
            # Try environment variable first
            self.api_key = os.getenv("OPENAI_API_KEY")
            
            # If not in env, try to import from credentials file
            if not self.api_key:
                try:
                    import openai_credentials
                    self.api_key = getattr(openai_credentials, "OPENAI_API_KEY", None)
                except ImportError:
                    pass
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable, "
                "or create openai_credentials.py with OPENAI_API_KEY, or pass it directly to OpenAIConfig."
            )

