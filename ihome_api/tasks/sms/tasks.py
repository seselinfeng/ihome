from ihome_api.libs.yuntongxun.sms import CCP
from ihome_api.tasks.main import celery_app


@celery_app.task
def send_template_sms(to, datas, temp_id):
    ccp = CCP()
    return ccp.send_template_sms(to, datas, temp_id)
