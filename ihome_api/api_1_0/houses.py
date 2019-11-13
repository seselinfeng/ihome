# coding:utf-8

from . import api
from flask import request, g, current_app, jsonify, session
from ihome_api import contants, db, redis_store
from ihome_api.utils.commons import login_required
from ihome_api.models import User, House, Area, Facility, HouseImage, Order
from ihome_api.utils.response_code import RET
from flask import json
from ihome_api.utils.image_storage import storage
from datetime import datetime
import os


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
    # # 上传房屋图片到七牛中
    # image_data = house_image.read()
    # try:
    #     file_name = storage(image_data)
    # except Exception as e:
    #     current_app.logger.error(e)
    #     return jsonify(errno=RET.THIRDERR, errmsg='文件上传失败')
    project_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    image_path = os.path.join(os.path.join(project_dir, contants.HOUSE_PATH), house_image.filename)
    if house_image is None:
        return jsonify(errno=RET.PARAMERR, errmsg='未上传图片')
    image_data = house_image.read()
    with open(image_path, 'wb') as f:
        f.write(image_data)
    # 把路径存储到房屋图片表中
    avatar_url = contants.HOUSE_PATH + house_image.filename
    # 保存图片信息到数据库中
    house_image = HouseImage(
        house_id=house_id,
        url=avatar_url
    )
    db.session.add(house_image)
    # 设置房屋的主图片
    if house.index_image_url == '':
        house.index_image_url = avatar_url
        current_app.logger.info('house % s' % house.__dict__)
        db.session.add(house)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')
    # image_url = contants.QINIU_URL_DOMAIN + file_name
    return jsonify(errno=RET.OK, errmsg='保存成功', data={'image_url': avatar_url})


#
# @api.route('/houses/<int:house_id>', methods=['GET'])
# @login_required
# def get_houses_detail(house_id):
#     """获取房源详情信息"""
#     user_id = g.user_id
#     current_app.logger.info('house_id2 %s' % house_id)
#     try:
#         house = House.query.filter(House.user_id == user_id, House.id == house_id).first()
#     except Exception as e:
#         current_app.logger.error(e)
#         return jsonify(errno=RET.DBERR, errmsg='数据库连接错误')
#     if house is None:
#         return jsonify(errno=RET.USERERR, errmsg='房源不存在')
#     return jsonify(errno=RET.OK, errmsg='查询成功', data={'user_id':user_id,'house': house.to_basic_dict()})


@api.route("/houses/<int:house_id>", methods=["GET"])
def get_house_detail(house_id):
    """获取房屋详情"""
    # 前端在房屋详情页面展示时，如果浏览页面的用户不是该房屋的房东，则展示预定按钮，否则不展示，
    # 所以需要后端返回登录用户的user_id
    # 尝试获取用户登录的信息，若登录，则返回给前端登录用户的user_id，否则返回user_id=-1
    user_id = session.get("user_id", "-1")

    # 校验参数
    if not house_id:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 先从redis缓存中获取信息
    try:
        ret = redis_store.get("house_info_%s" % house_id)
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    if ret:
        current_app.logger.info("hit house info redis")
        return '{"errno":"0", "errmsg":"OK", "data":{"user_id":%s, "house":%s}}' % (user_id, ret), 200, {
            "Content-Type": "application/json"}

    # 查询数据库
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

    if not house:
        return jsonify(errno=RET.NODATA, errmsg="房屋不存在")

    # 将房屋对象数据转换为字典
    try:
        house_data = bytes.decode(house.to_full_dict())
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="数据出错")

    # 存入到redis中
    json_house = json.dumps(house_data)
    try:
        redis_store.setex("house_info_%s" % house_id, contants.HOUSE_DETAIL_REDIS_EXPIRE_SECOND, json_house)
    except Exception as e:
        current_app.logger.error(e)

    resp = '{"errno":"0", "errmsg":"OK", "data":{"user_id":%s, "house":%s}}' % (user_id, json_house), 200, {
        "Content-Type": "application/json"}
    return resp


# GET /api/v1.0/houses?sd=&ed=&aid=&sk=&p=
@api.route('/houses', methods=['GET'])
def get_house_list():
    """获取房屋的列表信息（搜索页面）"""
    # 1. 获取参数
    start_date = request.args.get('sd', '')  # 用户筛选的起始时间
    end_date = request.args.get('ed', '')
    area_id = request.args.get('aid', '')
    sort_key = request.args.get('sk', 'new')
    page = request.args.get('p')

    # 2. 校验参数
    # 2.1 处理时间
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        if start_date and end_date:
            assert start_date <= end_date
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg='日期参数错误')
    # 2.2 判断区域ID
    if area_id:
        try:
            area = Area.query.get(area_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg='区域参数错误')
    # 2.3 处理页数
    if page:
        try:
            page = int(page)
        except Exception as e:
            current_app.logger.error(e)
            page = 1

    # 使用 redis 缓存数据
    redis_key = 'house_%s_%s_%s_%s' % (start_date, end_date, area_id, sort_key)
    try:
        resp_json = redis_store.hget(redis_key, page)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if resp_json:
            return resp_json, 200, {'Content-Type': 'application/json'}
    # 过滤条件的参数列表容器
    filter_params = []

    # 填充过滤参数
    conflict_orders = None
    try:
        if start_date and end_date:
            # 查询冲突的订单
            conflict_orders = Order.query.filter(Order.begin_date <= end_date, Order.end_date >= start_date).all()
        elif start_date:
            conflict_orders = Order.query.filter(Order.end_date >= start_date).all()
        elif end_date:
            conflict_orders = Order.query.filter(Order.begin_date <= end_date).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    if conflict_orders is not None:
        # 从订单中获取冲突的房屋id
        conflict_house_ids = [order.house_id for order in conflict_orders]

        if conflict_house_ids:
            filter_params.append(House.id.notin_(conflict_house_ids))
    # 区域条件
    if area_id:
        filter_params.append(House.area_id == area_id)

    # 3 查询数据库
    # 补充排序条件

    if sort_key == 'booking':  # 入住最多
        house_query = House.query.filter(*filter_params).order_by(House.order_count.desc())
    elif sort_key == 'price-inc':  # 价格由低到高
        house_query = House.query.filter(*filter_params).order_by(House.price.asc())
    elif sort_key == 'price-des':  # 价格由低到高
        house_query = House.query.filter(*filter_params).order_by(House.price.desc())
    else:  # 新旧
        house_query = House.query.filter(*filter_params).order_by(House.create_time.desc())

    # 处理分页
    try:
        page_obj = house_query.paginate(page, contants.HOUSE_LIST_PAGE_CAPACITY, error_out=False)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    # 获取页面数据
    house_li = page_obj.items
    houses = []
    for house in house_li:
        houses.append(house.to_basic_dict())
    # 获取总页数
    total_page = page_obj.pages
    resp_dict = dict(
        errno=RET.OK, errmsg='ok', data={'total_page': total_page, 'houses': houses, 'current_page': page})
    resp_json = json.dumps(resp_dict)
    if page <= total_page:
        # 设置redis key
        redis_key = 'house_%s_%s_%s_%s' % (start_date, end_date, area_id, sort_key)
        try:
            # 创建redis管道对象，可以执行多个语句
            pipeline = redis_store.pipeline()
            # 开启多语句的记录
            pipeline.multi()
            pipeline.hset(redis_key, page, resp_json)
            pipeline.expire(redis_key, contants.HOUSE_LIST_PAGE_REDIS_CACHE_EXPIRES)
            # 执行语句
            pipeline.excute()
        except Exception as e:
            current_app.logger.error(e)
        # return jsonify(errno=RET.OK, errmsg='ok', data={'total_page': total_page, 'houses': houses, 'current_page': page})
    return resp_json, 200, {'Content-Type': 'application/json'}


@api.route("/houses/index", methods=["GET"])
def get_house_index():
    """获取主页幻灯片展示的房屋基本信息"""
    # 从缓存中尝试去除数据
    try:
        ret = redis_store.get('home_page_data')
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    if ret:
        current_app.logger.info("hit house index info redis")
        # 因为redis中保存的是json字符串，所以直接进行字符串拼接返回
        return '{"errno":0, "errmsg":"OK", "data":%s}' % ret, 200, {"Content-Type": "application/json"}
        # 查询数据库，返回房屋订单数目最多的5条数据
    try:
        houses = House.query.order_by(House.order_count.desc()).limit(contants.HOME_PAGE_MAX_HOUSES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库错误')
    if not houses:
        return jsonify(errno=RET.NODATA, errmsg='暂无数据')
    # 如果房屋未设置主图片，则跳过
    house_list = []
    for house in houses:
        if not house.index_image_url:
            continue
        house_list.append(house.to_basic_dict())
    houses_json = json.dumps(house_list)
    try:
        redis_store.setex('home_page_data', contants.HOME_PAGE_DATA_REDIS_EXPIRES, houses_json)
    except Exception as e:
        current_app.logger.error(e)

    # 将数据转换为json，并保存到redis缓存
    return '{"errno":0,"errmsg":"OK",data:%s}' % houses_json, 200, '{"Content-Type:"application/json"}'
