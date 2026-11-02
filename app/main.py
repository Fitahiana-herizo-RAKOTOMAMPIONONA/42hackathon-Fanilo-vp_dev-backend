from fastapi import FastAPI

from app.bootstrap import create_app

app: FastAPI = create_app()
