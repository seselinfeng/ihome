# coding:utf-8
from . import api
from ihome_api import db
from flask import current_app


@api.route('/index')
def hello_world():
    current_app.logger.error('error msg')
    current_app.logger.warn('warn msg')
    current_app.logger.info('info msg')
    current_app.logger.debug('debug msg')
    db.create_all()
    return 'Hello World!'
