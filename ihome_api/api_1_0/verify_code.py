# coding:utf-8
from flask import current_app, jsonify, make_response, request
from . import api
from ihome_api.utils.captcha.captcha import captcha
from ihome_api.utils.response_code import RET
from ihome_api import redis_store
from ihome_api import contants
from ihome_api.models import User
import random
from ihome_api.libs.yuntongxun.sms import CCP
from ihome_api.tasks.sms import tasks


# GET 127.0.0.1/api/v1.0/image_codes/<image_code_id>
@api.route('/image_codes/<image_code_id>')
def get_image_code(image_code_id):
    """获取图片验证码
    :param image_code_id:图片验证码编号
    :return 正常：验证码图片  异常：返回json
    """
    # 提取参数
    # 检验参数
    # 1. 业务逻辑处理
    # 1.1 生成验证码图片
    # 名字 真实文本 图片数据
    name, text, image_data = captcha.generate_captcha()
    # 1.2 将验证码真实值和编码保存到redis中，设置有效期
    # Redis 数据类型：字符串 列表 哈希 集合 有序集合
    # 'key':xxx
    # 使用哈希维护有效期的时候只能整体设置
    # 'image_code':['编号1':'真实值1','编号2':'真实值2'] 哈希 hset('image_codes','id1','abc) hget('image_codes','id1')
    # 单条维护记录，选用字符串类型
    # 'image_code_编号':'真实值'
    try:
        # redis_store.set('image_code_%s' % image_code_id, text)
        # redis_store.expire('image_code_%s' % image_code_id, contants.IMAGE_CODE_REDIS_EXPIRES)
        redis_store.setex('image_code_%s' % image_code_id, time=contants.IMAGE_CODE_REDIS_EXPIRES, value=text)
    except Exception as e:
        # 记录日志
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='save image code id failed')
    # 返回值
    # 1.3 返回图片
    resp = make_response(image_data)
    resp.headers['Content-Type'] = 'image/jpg'
    return resp


# GET /api/v1.0/sms_codes/<mobile>?image_code = xxx&image_code_id=xxx
@api.route("/sms_codes/<re(r'1[34578]\d{9}'):mobile>")
def get_sms_code(mobile):
    """获取短信验证码"""
    # 获取参数
    image_code = request.args.get('image_code')
    image_code_id = request.args.get('image_code_id')
    # 校验参数
    if not all((image_code_id, image_code)):
        # 表示参数不完整
        return jsonify(error=RET.PARAMERR, errmsg='参数不完整')
    # 业务逻辑处理
    # 1. 从redis中取出真实图片验证码
    try:
        real_image_code = redis_store.get('image_code_%s' % image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='redis数据库异常')
    if real_image_code is None:
        # 图片验证码没有或者过期
        return jsonify(errno=RET.NODATA, errmsg='图片验证码失效')
    # 2. 进行对比
    if real_image_code.decode("utf-8").lower() != image_code.lower():
        return jsonify(errno=RET.DATAERR, errmsg='图片验证码错误')
    # 删除redis中的图片验证码，防止用户使用同一个图片验证码验证多次
    try:
        redis_store.delete('image_code_%s' % image_code_id)
    except Exception as e:
        current_app.logger.error(e)
    # 判断对于这个手机号的操作，在60秒内有没有之前的记录，如果有，则认为用户操作频繁，不处理
    try:
        send_flag = redis_store.get('send_sms_code_%s' % mobile)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if send_flag is not None:
            return jsonify(errno=RET.REQERR, errmsg='请求过于频繁')
    # 3. 校验手机号是否存在
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='mysql数据库异常')
    else:
        if user is not None:
            return jsonify(errno=RET.DATAEXIST, errmsg='手机号已经被注册')
    # 4. 生成短信验证码
    sms_code = "%06d" % random.randint(100000, 999999)
    # 5. 保存真实验证码
    try:
        redis_store.setex('sms_code_%s' % mobile, contants.SMS_CODE_REDIS_EXPIRES, sms_code)
        # 保存发送给这个手机号的记录，防止用户在60秒内再次触发发送短信操作
        redis_store.setex('send_sms_code_%s' % mobile, contants.SEND_SMS_CODE_INTERVAL, 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='保存短信验证码异常')
    # 6. 发送
    result = tasks.send_template_sms.delay(mobile, [sms_code, int(contants.SMS_CODE_REDIS_EXPIRES / 60)], 1)
    # ccp = CCP()
    # try:
    #     result = ccp.send_template_sms(mobile, [sms_code, int(contants.SMS_CODE_REDIS_EXPIRES / 60)], 1)
    # except Exception as e:
    #     current_app.logger.error(e)
    #     return jsonify(errno=RET.THIRDERR, errmsg='发送异常')
    # 返回值 没注册 用失败当成功
    # if result != 0:
    #     return jsonify(errno=RET.OK, errmsg="发送成功")
    # else:
    #     return jsonify(errno=RET.THIRDERR, errmsg='发送失败')
    # get 方法默认是阻塞行为，会等到有结果才返回
    # get 方法可以设置参数timeout，超时时间，如果超时则返回
    ret = result.get()
    current_app.logger.info(ret)
    return jsonify(errno=RET.OK, errmsg="发送成功")
