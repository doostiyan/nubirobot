from .main import env

DATABASES = {
    'default': env.db()
}

ENABLE_REPLICA = env.bool('ENABLE_REPLICA', default=False)
if ENABLE_REPLICA:
    DATABASES['replica'] = env.db('REPLICA_DB_URL')
    DATABASE_ROUTERS = ['exchange.routers.db_router.PrimaryReplicaRouter']


ENABLE_HIGH_TX_NETWORKS_DB = env.bool('ENABLE_HIGH_TX_NETWORKS_DB', default=False)
if ENABLE_HIGH_TX_NETWORKS_DB:
    DATABASES['high_tx'] = env.db('HIGH_TX_DB_URL')
    DATABASE_ROUTERS = ['exchange.routers.db_router.PrimaryReplicaRouter']
