# coding:utf-8
from . import api
from flask import request, jsonify, current_app, session
from ihome_api.utils.response_code import RET
from ihome_api import redis_store, db
from ihome_api.models import User
from sqlalchemy.exc import IntegrityError
from ihome_api import contants
import re


@api.route('users', methods=['POST'])
def register():
    """注册
    @:param 手机号、短信验证码、密码、确认密码
    @:type json
    @:return json
    """
    # 获取请求的json数据
    req_dict = request.get_json()
    mobile = req_dict.get('mobile')
    sms_code = req_dict.get('sms_code')
    password = req_dict.get('password')
    password2 = req_dict.get('password2')
    if not all((mobile, sms_code, password)):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')
    # 判断手机号格式
    if not re.match(r'1[345678]\d{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg='手机号格式错误')
    # 判断两次密码
    if password != password2:
        return jsonify(errno=RET.PARAMERR, errmsg='两次密码不一致')
    # 验证短信验证码
    # 判断短信验证码是否过期
    try:
        real_sms_code = bytes.decode(redis_store.get('sms_code_%s' % mobile))
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='读取短信验证码异常')
    else:
        if real_sms_code is None:
            return jsonify(errno=RET.NODATA, errmsg='短信验证码失效')
        # 删除redis中的短信验证码，防止重复使用校验
        try:
            redis_store.delete('sms_code_%s' % mobile)
        except Exception as e:
            current_app.logger.error(e)
        if real_sms_code != sms_code:
            current_app.logger.info("real_sms_code %s" % real_sms_code)
            current_app.logger.info("sms_code %s" % sms_code)
            return jsonify(errno=RET.DATAERR, errmsg='短信验证码错误')
    # 判断手机号是否注册
    # try:
    #     user = User.query.filter_by(mobile=mobile).first()
    # except Exception as e:
    #     current_app.logger.error(e)
    #     return jsonify(errno=RET.DBERR, errmsg='查询数据库异常')
    # else:
    #     if user is not None:
    #         return jsonify(errno=RET.DATAERR, errmsg='手机号已经被注册')
    # # 保存用户的注册数据到数据库中
    user = User(name=mobile, mobile=mobile)
    user.password = password
    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg='手机号已经被注册')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询数据库异常')
    # 保存登录状态到session中
    session['name'] = mobile
    session['mobile'] = mobile
    session['user_id'] = user.id
    # 返回结果

    return jsonify(errno=RET.OK, errmsg='注册成功')


@api.route('/sessions', methods=['POST'])
def login():
    """登录
    @:param 手机号、密码
    @:type json
    @:return json
    """
    # 获取请求的json数据
    req_dict = request.get_json()
    mobile = req_dict.get('mobile')
    password = req_dict.get('password')
    # 校验参数
    # 参数完整的校验
    if not all((mobile, password)):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')
    # 手机号格式
    if not re.match(r'1[34578]\d{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg='手机格式错误')
    # 判断错误次数，如果超过限制则限制登录
    # redis记录： "access_count_ip":次数
    user_ip = request.remote_addr
    try:
        access_nums = redis_store.get('access_count_%s' % user_ip)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if access_nums is not None and int(access_nums) >= contants.LOGIN_ERROR_MAX_TIMES:
            return jsonify(errno=RET.REQERR, errmsg="密码错误次数过多，请稍后重试")
    # 查询用户数据库密码
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='获取用户信息失败')
    if user is None or not user.check_password(password):
        # 失败，记录错误次数，返回信息
        try:
            redis_store.incr("access_num_%s" % user_ip)
            redis_store.expire("access_num_%s" % user_ip, contants.LOGIN_ERROR_FORBID_TIME)
        except Exception as e:
            current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg='用户名或密码错误')
    # 成功，保存登录状态在session中
    session['name'] = user.name
    session['mobile'] = user.mobile
    session['user_id'] = user.id
    return jsonify(errno=RET.OK, errmsg='登陆成功')


@api.route('/sessions', methods=['GET'])
def check_login():
    """检查登录状态"""
    name = session.get('name')
    if name is not None:
        return jsonify(errno=RET.OK, errmsg='true', data={'name': name})
    else:
        return jsonify(errno=RET.SESSIONERR, errmsg='false')


@api.route('/sessions', methods=['DELETE'])
def logout():
    """退出登录"""
    session.clear()
    return jsonify(errno=RET.OK, errmsg='OK')
