"""FinSight shared library.

Code that more than one service needs lives here: settings, domain models,
PII redaction, statement parsing, categorization, and the LLM provider
abstraction. Keep heavy/optional imports (pandas, presidio, openai) inside
functions so importing this package stays cheap.
"""

from .config import Settings, get_settings
from .models import Category, Statement, Transaction

__all__ = ["Category", "Statement", "Transaction", "Settings", "get_settings"]
__version__ = "0.1.0"
