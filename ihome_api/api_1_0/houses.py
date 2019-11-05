# coding:utf-8

from . import api
from flask import request, g, current_app, jsonify
from ihome_api import contants, db, redis_store
from ihome_api.utils.commons import login_required
from ihome_api.models import User, House, Area, Facility, HouseImage
from ihome_api.utils.response_code import RET
from flask import json
from ihome_api.utils.image_storage import storage


@api.route('/user/houses', methods=['GET'])
@login_required
def get_houses():
    """获取用户的房源信息"""
    user_id = g.user_id
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库连接错误')
    if user is None:
        return jsonify(errno=RET.USERERR, errmsg='用户不存在')
    houses = user.houses
    # 将查询到的房屋信息转换为字典存放到列表中
    houses_list = []
    if houses:
        for house in houses:
            houses_list.append(house.to_basic_dict())
    return jsonify(errno=RET.OK, errmsg='查询房屋成功', data={'houses': houses_list})


@api.route('/areas', methods=['GET'])
@login_required
def get_areas():
    """获取城区信息"""
    # 尝试从redis中获取城区信息
    try:
        areas_json = redis_store.get('areas_info')
    except Exception as e:
        current_app.logger.error(e)
    if areas_json is None:
        # 从数据库获取城区信息
        try:
            areas = Area.query.all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg='数据库连接异常')
        area_dict = []
        for area in areas:
            area_dict.append(area.to_dict_area())
        areas_json = json.dumps(area_dict)
        # 存储到redis中
        try:
            redis_store.setex('areas_info', contants.AREAS_REDIS_EXPIRES, value=areas_json)
        except Exception as e:
            current_app.logger.error(e)
    else:
        # 表示redis中有缓存，直接使用的是缓存数据
        areas_json = areas_json.decode("utf-8")
        current_app.logger.info("hit redis cache area info")
    return '{"errno": 0, "errmsg": "查询城区信息成功", "data":{"areas": %s}}' % areas_json, 200, {
        "Content-Type": "application/json"}


@api.route('/houses/info', methods=['POST'])
@login_required
def set_houses_info():
    """保存房屋的基本信息
    前端发送过来的json数据
    {
        "title":"",
        "price":"",
        "area_id":"1",
        "address":"",
        "room_count":"",
        "acreage":"",
        "unit":"",
        "capacity":"",
        "beds":"",
        "deposit":"",
        "min_days":"",
        "max_days":"",
        "facility":["7","8"]
    }
    """
    house_data = request.get_json()
    if house_data is None:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    title = house_data.get("title")  # 房屋名称标题
    price = house_data.get("price")  # 房屋单价
    area_id = house_data.get("area_id")  # 房屋所属城区的编号
    address = house_data.get("address")  # 房屋地址
    room_count = house_data.get("room_count")  # 房屋包含的房间数目
    acreage = house_data.get("acreage")  # 房屋面积
    unit = house_data.get("unit")  # 房屋布局（几室几厅)
    capacity = house_data.get("capacity")  # 房屋容纳人数
    beds = house_data.get("beds")  # 房屋卧床数目
    deposit = house_data.get("deposit")  # 押金
    min_days = house_data.get("min_days")  # 最小入住天数
    max_days = house_data.get("max_days")  # 最大入住天数
    if not all(
            (title, price, area_id, address, room_count, acreage, unit, capacity, beds, deposit, min_days, max_days)):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')
    # 判断单价和押金格式是否正确
    # 前端传送过来的金额参数是以元为单位，浮点数，数据库中保存的是以分为单位，整数
    try:
        price = int(float(price) * 100)
        deposit = int(float(deposit) * 100)
    except Exception as e:
        return jsonify(errno=RET.DATAERR, errmsg="参数有误")
    user_id = g.user_id
    house = House(user_id=user_id,
                  area_id=area_id,
                  title=title,
                  price=price,
                  address=address,
                  room_count=room_count,
                  acreage=acreage,
                  unit=unit,
                  capacity=capacity,
                  beds=beds,
                  deposit=deposit,
                  min_days=min_days,
                  max_days=max_days)
    # 处理房屋的设施信息
    facility_id_list = house_data.get('facility')
    if facility_id_list:
        try:
            facility_list = Facility.query.filter(Facility.id.in_(facility_id_list)).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据库错误")
        if facility_list:
            house.facilities = facility_list
    try:
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库错误")
    return jsonify(errno=RET.OK, errmsg='发布房源成功', data={'house_id': house.id})


@api.route('/houses/image', methods=['POST'])
@login_required
def set_houses_image():
    """设置房源图片"""
    house_id = request.form.get('house_id')
    house_image = request.files.get('house_image')
    if not all((house_id, house_image)):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')
    # 判断房屋是否存在
    try:
        house = House.query.filter_by(id=house_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库连接异常')
    if house is None:
        return jsonify(errno=RET.NODATA, errmsg='房源不存在')
    # 上传房屋图片到七牛中
    image_data = house_image.read()
    try:
        file_name = storage(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg='文件上传失败')
    # 保存图片信息到数据库中
    house_image = HouseImage(
        house_id=house_id,
        url=file_name
    )
    db.session.add(house_image)
    if house.index_image_url is None:
        house.index_image_url = file_name
        db.session.add(house)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    image_url = contants.QINIU_URL_DOMAIN + file_name
    return jsonify(errno=RET.OK, errmsg='保存成功', data={'image_url': image_url})
