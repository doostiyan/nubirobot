import os

MESSAGE_BROKERS = {
    "rabbitmq": {
        "HOST": os.environ.get("MESSAGE_BROKER_HOST", "localhost"),
        "PORT": os.environ.get("MESSAGE_BROKER_PORT", 5672),
        "USERNAME": os.environ.get("MESSAGE_BROKER_USERNAME", "guest"),
        "PASSWORD": os.environ.get("MESSAGE_BROKER_PASSWORD", "guest"),
        "USE_PROXY": True if os.environ.get("MESSAGE_BROKER_USE_PROXY", False) == "True" else False
    }
}
