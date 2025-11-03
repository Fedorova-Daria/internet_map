from celery import shared_task


@shared_task
def say_hello():
    return "привет, мир"

