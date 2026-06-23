import os

import redis


def get_database_connection():
    redis_password = os.environ.get("REDIS_PASSWORD") or None

    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=redis_password,
        decode_responses=True,
    )


def connect_to_database():
    redis_database = get_database_connection()
    redis_database.ping()
    return redis_database
