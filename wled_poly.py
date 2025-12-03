#!/usr/bin/env python3
"""
WLED Polyglot NodeServer

A Polyglot v3 (PG3) NodeServer for Universal Devices ISY that provides 
full control of WLED LED controllers.

Features:
- Multi-device support (control multiple WLED devices from one nodeserver)
- mDNS device discovery
- Full WLED JSON API integration
- Control: On/Off, Brightness, Effects, Palettes, Presets, RGB Color
- Segment-level control

Author: Seth Kaplan
License: MIT
"""

import udi_interface
import sys
import time
import json
import logging

# Import node classes
from nodes import Controller

LOGGER = udi_interface.LOGGER

VERSION = '1.5.2'


def main():
    """
    Main entry point for the WLED NodeServer.
    
    Initializes the Polyglot interface and creates the controller node.
    """
    LOGGER.info(f"WLED NodeServer v{VERSION} starting...")
    
    try:
        # Initialize Polyglot interface
        polyglot = udi_interface.Interface([])
        polyglot.start(VERSION)
        
        # Wait for interface to be ready
        polyglot.updateProfile()
        polyglot.setCustomParamsDoc()
        
        # Create controller node
        controller = Controller(
            polyglot,
            'controller',
            'controller',
            'WLED Controller'
        )
        
        LOGGER.info("WLED NodeServer started successfully")
        
        # Run until stopped
        polyglot.runForever()
        
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("WLED NodeServer shutting down...")
        sys.exit(0)
        
    except Exception as e:
        LOGGER.error(f"WLED NodeServer failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

