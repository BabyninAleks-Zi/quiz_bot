import redis


def get_database_connection(host, port, password=None, db=0):
    return redis.Redis(
        host=host,
        port=port,
        password=password,
        db=db,
        decode_responses=True,
    )


def connect_to_database(host, port, password=None, db=0):
    redis_database = get_database_connection(host, port, password, db)
    redis_database.ping()
    return redis_database
