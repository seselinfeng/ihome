from werkzeug.routing import BaseConverter
from flask import session, jsonify, g
from ihome_api.utils.response_code import RET
from functools import wraps


class ReConverter(BaseConverter):
    def __init__(self, url_map, regex):
        super(ReConverter, self).__init__(url_map)
        self.regex = regex


# 验证登录状态的装饰器
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        # 判断用户的登录状态
        user_id = session.get('user_id')
        if user_id is not None:
            # g对象，全局中间对象
            g.user_id = user_id
            return view_func(*args, **kwargs)
        else:
            return jsonify(errno=RET.SESSIONERR, errmsg='用户未登录')

    return wrapper
