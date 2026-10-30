"""Backward-compatible import location for MongoDB lifecycle helpers."""
from app.db.mongo import connect_mongo, close_mongo, get_database

__all__ = ["connect_mongo", "close_mongo", "get_database"]
