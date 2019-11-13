import datetime
from flask import request, g, jsonify, current_app
from ihome_api import db, redis_store
from ihome_api.utils.commons import login_required
from ihome_api.utils.response_code import RET
from ihome_api.models import House, Order
from . import api


@api.route('/orders', methods=['POST'])
@login_required
def save_order():
    """生成订单"""
    user_id = g.user_id
    order_data = request.get_json()
    if not order_data:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    house_id = order_data.get('house_id')
    start_date_str = order_data.get('start_date')
    end_date_str = order_data.get('end_date')

    if not all((house_id, start_date_str, end_date_str)):
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')

    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
        assert start_date <= end_date
        days = end_date - start_date + 1
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    # 查询房屋是否存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    if not house:
        return jsonify(errno=RET.NODATA, errmsg='房屋不存在')
    # 预定的房屋是否是房东自己的
    if house.user_id == user_id:
        return jsonify(errno=RET.ROLEERR, errmsg='不能预定自己的房屋')
    # 确保用户预定的时间内 房屋没有被别人预定
    try:
        count = Order.query.filter(
            Order.house_id == house_id, Order.begin_date <= end_date, Order.end_date >= start_date).count()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    if count > 0:
        return jsonify(errno=RET.DATAEXIST, errmgs='房屋已经被预定啦')
    # 订单总额
    amount = house.price * days

    # 保存订单数据
    order = Order(house_id=house_id,
                  user_id=user_id,
                  begin_date=start_date,
                  end_date=end_date,
                  days=days,
                  house_price=house.price,
                  amount=amount)
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    return jsonify(errno=RET.OK, errmsg='预定成功', data={'order_id': order.id})


@api.route('/user/orders', methods=['GET'])
@login_required
def get_user_orders():
    """获取用户订单"""
    user_id = g.user_id

    # 获取用户身份
    role = request.args.get('role', '')
    # 查询订单数据
    try:
        if 'landlord' == role:
            # 以房东的身份查询
            # 先查询属于自己的房子有哪些
            houses = House.query.filter(House.user_id == user_id).all()
            house_ids = [house.id for house in houses]
            # 再查询预定自己的房子的订单
            orders = Order.query.filter(Order.id.in_(house_ids)).order_by(Order.create_time)
        # 以房客的身份查询
        else:
            orders = Order.query.filter(Order.user_id == user_id).order_by(Order.create_time)

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询失败')
    # 将订单转换为字典数据
    orders_dict_list = []
    for order in orders:
        orders_dict_list.append(order.to_basic_dict())
    return jsonify(errno=RET.OK, errmgs='查询成功', data={'orders': orders_dict_list})


@api.route('/orders/<int:order_id>/status', methods=['PUT'])
@login_required
def accept_reject_order(order_id):
    """接单、拒单"""
    user_id = g.user_id
    req_data = request.get_json()
    if not req_data:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # action参数表明客户端请求的是接单还是拒单的行为
    action = req_data.get('action')
    if action not in ['accept,reject']:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 根据订单号查询订单，并且要求订单处于等待接单状态
    try:
        order = Order.query.filter(Order.id == order_id, Order.status == "WAIT_ACCEPT").first()
        house = order.house
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    # 确保房东只能修改属于自己房子的订单
    if not order or house.user_id != user_id:
        return jsonify(errno=RET.REQERR, errmsg='操作无效')
    # 接单，将订单状态设置为等待评论
    if action == 'accept':
        order.status = 'WAIT_PAYMENT'
    # 拒单，要求用户传递拒单原因
    elif action == 'reject':
        reason = req_data.get('reason')
        if not reason:
            return jsonify(errno=RET.PARAMERR, errmsg='请输入理由')
        order.status = 'REJECTED'
        order.comment = reason
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    return jsonify(errno=RET.OK, errmsg='OK')


@api.route("/orders/<int:order_id>/comment", methods=["PUT"])
@login_required
def save_order_comment(order_id):
    """保存评论信息"""
    # 获取参数
    user_id = g.user_id
    req_data = request.get_json()
    comment = req_data.get('comment')

    # 检查参数
    if not comment:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')

    # 需要确保只能评论自己下的订单，而且订单处于待评价状态
    try:
        order = Order.query.filter(Order.id == order_id, Order.status == 'WAIT_COMMENT').first()
        house = order.house
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    if not order:
        return jsonify(errno=RET.PARAMERR, errmsg='不能评价他人订单')

    # 将订单设为已完成
    order.status = 'COMPLETE'
    # 保存评价信息
    order.comment = comment
    # 房屋评价数+1
    house.order_count += 1
    try:
        db.session.add(order)
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    # 因为房屋详情中有订单的评价信息，为了让最新的评价信息展示在房屋详情中，所以删除redis中关于本订单房屋的详情缓存
    try:
        redis_store.delete('house_info_%s' % order.house.id)
    except Exception as e:
        current_app.logger.error(e)
    return jsonify(errno=RET.OK, errmsg='OK')
