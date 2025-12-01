#!/usr/bin/env bash

# WLED Polyglot NodeServer Installation Script

set -e

echo "Installing WLED NodeServer dependencies..."

# Upgrade pip first
pip3 install --upgrade pip

# Install requirements
pip3 install -r requirements.txt

echo "WLED NodeServer installation complete!"

