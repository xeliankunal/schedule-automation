#!/usr/bin/env python3
"""
Test Schedule Reader - Runs immediately regardless of time
"""

import os
import sys

# Set the environment to test mode
os.environ['TEST_MODE'] = 'true'

# Import and run the main schedule reader
from scheduler_reader import main

if __name__ == '__main__':
    print("🧪 Running schedule reader in test mode...")
    print("This will process tomorrow's schedule immediately")
    print("=" * 50)
    main()