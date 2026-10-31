"""Vercel serverless entrypoint for the PlacePrep AI API.

Vercel's Python runtime turns files under api/ into serverless functions.
This module exposes the FastAPI app from ../main.py so every API route is
served by this function (see vercel.json rewrites). The same main.py still
runs standalone with uvicorn for local development and other hosts.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402,F401
