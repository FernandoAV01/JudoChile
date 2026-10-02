"""Punto de entrada del servidor: gunicorn wsgi:app"""
from judo import create_app

app = create_app()
