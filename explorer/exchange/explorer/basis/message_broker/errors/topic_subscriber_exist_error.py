class TopicSubscriberExistError(Exception):
    def __init__(self, topic: str) -> None:
        super().__init__(f"subscriber for topic : {topic} already exists!")
