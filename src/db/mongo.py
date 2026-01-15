import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv('MONGODB_URI')


mongoClient = AsyncIOMotorClient(MONGODB_URI)