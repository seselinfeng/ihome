# coding:utf-8
from . import api
from ihome_api.utils.commons import login_required
from flask import g, current_app, jsonify, request, session
from ihome_api.utils.response_code import RET
from ihome_api.utils.image_storage import storage
from ihome_api.models import User
from ihome_api import db, redis_store
from ihome_api import contants
from sqlalchemy.exc import IntegrityError
import os


#
# @api.route('/users/avatar', methods=['POST'])
# @login_required
# def set_user_avatar():
#     """设置用户的头像
#     @:param 图片（多媒体表单）、用户ID(g对象)
#     """
#     user_id = g.user_id
#     image_file = request.files.get('avatar')
#     if image_file is None:
#         return jsonify(errno=RET.PARAMERR, errmsg='未上传图片')
#
#     image_data = image_file.read()
#     # 调用七牛上传图片
#     try:
#         file_name = storage(image_data)
#     except Exception as e:
#         current_app.logger.error(e)
#         return jsonify(errno=RET.THIRDERR, errmsg='图片上传异常')
#     # 保存文件名到数据库中
#     try:
#         User.query.filter_by(id=user_id).update({"avatar_url": file_name})
#         db.session.commit()
#     except Exception as e:
#         db.session.rollback()
#         current_app.logger.error(e)
#         return jsonify(errno=RET.DBERR, errmsg='保存图片失败')
#
#     return jsonify(errno=RET.OK, errmsg='保存成功', data={'avatar_url': contants.QINIU_URL_DOMAIN + file_name})

@api.route('/users/avatar', methods=['POST'])
@login_required
def set_user_avatar():
    """设置用户的头像
    @:param 图片（多媒体表单）、用户ID(g对象)
    """
    user_id = g.user_id
    image_file = request.files.get('avatar')
    project_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    image_path = os.path.join(os.path.join(project_dir, contants.USER_PATH), image_file.filename)
    if image_file is None:
        return jsonify(errno=RET.PARAMERR, errmsg='未上传图片')
    image_data = image_file.read()
    current_app.logger.info(image_file.__dict__)
    with open(image_path, 'wb') as f:
        f.write(image_data)
    # 把路径存储到用户表中
    avatar_url = contants.USER_PATH + image_file.filename
    try:
        user = User.query.filter_by(id=user_id).first()
        user.avatar_url = avatar_url
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    return jsonify(errno=RET.OK, errmsg='保存成功', data={'avatar_url': contants.USER_PATH + image_file.filename})


@api.route('/users/name', methods=['PUT'])
@login_required
def set_user_name():
    """设置用户名
    @:param 用户名称、用户ID(g对象)
    """
    user_id = g.user_id
    req_dict = request.get_json()
    user_name = req_dict.get('name')
    if not all((user_name,)):
        return jsonify(errno=RET.PARAMERR, errmsg='用户名称不能为空')
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='获取用户信息失败')
    if user is None:
        return jsonify(errno=RET.USERERR, errmsg='用户不存在，请退出重试')
    user.name = user_name
    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAEXIST, errmsg='用户名称已存在，请重新输入')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    redis_store.setex('user_name_%s' % user_id, time=contants.USER_NAME_REDIS_EXPIRES, value=user_name)
    session['name'] = user_name
    return jsonify(errno=RET.OK, errmsg='保存成功')


@api.route('/user', methods=['GET'])
@login_required
def get_user():
    """获取用户信息
    @:param 用户ID
    """
    use_id = g.user_id
    try:
        user = User.query.filter_by(id=use_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    if user is None:
        return jsonify(errno=RET.USERERR, errmsg='用户不存在')
    return jsonify(errno=RET.OK, errmsg='查询成功', data=user.to_dict())


@api.route('/user/auth', methods=['GET'])
@login_required
def get_user_auth():
    """查询用户实名信息"""
    user_id = g.user_id
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库查询异常')
    return jsonify(errno=RET.OK, errmsg='查询用户实名信息成功', data=user.auth_to_dict())


@api.route('user/auth', methods=['POST'])
@login_required
def set_user_auth():
    """设置用户实名信息"""
    user_id = g.user_id
    resp_dict = request.get_json()
    real_name = resp_dict.get('real_name')
    id_cast = resp_dict.get('id_card')
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库查询异常')
    if user is None:
        return jsonify(errno=RET.USERERR, errmsg='用户不存在')
    user.id_card = id_cast
    user.real_name = real_name
    try:
        db.session.add(user)
        # User.query.filter_by(id=user_id, real_name=None, id_card=None).update({"real_name": real_name, "id_card": id_card})
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    return jsonify(errno=RET.OK, errmsg='实名认证成功')
