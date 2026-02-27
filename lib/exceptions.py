"""
lib/exceptions.py

Custom exception definitions
"""

import warnings

class StateChangeError(Exception):
    """ Raised when starting, stopping, or restarting the DNS server fails
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class ConfigurationError(Exception):
    """ Raised when an error occurs reading or writing a configuration file
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
