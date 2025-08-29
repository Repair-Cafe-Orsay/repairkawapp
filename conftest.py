# Configure PYTHONPATH pour permettre l'import du package local quand pytest est lancé
import os
import sys

root = os.path.abspath(os.path.dirname(__file__))
if root not in sys.path:
    sys.path.insert(0, root)
