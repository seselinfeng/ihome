# -*- coding：utf-8 -*-

from ihome_api import db
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import constants


class BaseModel(object):
    """模型基类，为每个模型补充创建时间与更新时间"""
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class User(BaseModel, db.Model):
    """用户"""
    __tablename__ = 'ih_user_profile'
    id = db.Column(db.Integer, primary_key=True)  # 用户编号
    name = db.Column(db.String(32), unique=True, nullable=False)  # 用户昵称
    password_hash = db.Column(db.String(128), nullable=False)  # 用户加密的密码
    mobile = db.Column(db.String(11), unique=True, nullable=False)  # 手机号
    real_name = db.Column(db.String(32))  # 真实姓名
    id_card = db.Column(db.String(20))  # 身份证号
    avatar_url = db.Column(db.String(128))  # 用户头像路径
    houses = db.relationship('House', backref='user')  # 用户发布的房屋
    orders = db.relationship('Order', backref='user')  # 用户订单

    @property
    def password(self):
        """获取password属性时被调用"""
        raise AttributeError('不可读')

    @property.setter
    def password(self, password):
        """设置password属性时被调用，设置密码加密"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """检查密码的正确性"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """将对象转换为字典数据"""
        user_dict = {
            'user_id': self.id,
            'name': self.name,
            'mobile': self.mobile,
            'avatar': constants.QINIU_URL_DOMAIN + self.user.avatar_url if self.user.avatar_url else "",
            'create_time': self.create_time.strftime('%Y-%M-%D %H:%M:%S')
        }
        return user_dict

    def auth_to_dict(self):
        """将实名信息转换为字典数据"""
        auth_dict = {
            'user_id': self.id,
            'real_name': self.real_name,
            'id_card': self.id_card
        }
        return auth_dict


class Area(BaseModel, db.Model):
    """城区"""
    __tablenam__ = 'ih_area_info'
    
