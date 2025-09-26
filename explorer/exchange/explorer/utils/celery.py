from exchange.explorer.utils.cache import redis_client


def get_task_count_by_queue(queue_name):
    tasks = redis_client.lrange(queue_name, 0, -1)
    return len(tasks)