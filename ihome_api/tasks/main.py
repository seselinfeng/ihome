# coding:utf-8
from celery import Celery
from ihome_api.tasks import config

celery_app = Celery('ihome')
celery_app.config_from_object(config)
# celery自动寻找任务
celery_app.autodiscover_tasks(['ihome_api.tasks.sms'])
