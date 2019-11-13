# coding:utf-8

# 图片验证码的redis有效期,单位秒
IMAGE_CODE_REDIS_EXPIRES = 180
# 短信验证码的redis有效期,单位秒
SMS_CODE_REDIS_EXPIRES = 300
# 发送短信验证码的间隔
SEND_SMS_CODE_INTERVAL = 60
# 密码错误尝试次数
LOGIN_ERROR_MAX_TIMES = 5
# 登录错误限制的时间
LOGIN_ERROR_FORBID_TIME = 600
# 七牛域名
QINIU_URL_DOMAIN = 'http://o91qujnqh.bkt.cloudcn.com/'
# 用户名保存时间
USER_NAME_REDIS_EXPIRES = 300
# 城区信息有效期
AREAS_REDIS_EXPIRES = 7200
# 用户头像图片存储本地路径
USER_PATH = 'static/images/user_image/'
# 房源信息图像存储本地路径
HOUSE_PATH = 'static/images/house_image/'
# 房屋列表页面每页数据容量
HOUSE_LIST_PAGE_CAPACITY = 2
# 房屋列表页面页数缓存时间，单位秒
HOUSE_LIST_PAGE_REDIS_CACHE_EXPIRES = 7200
# 首页展示最多的房屋数量
HOME_PAGE_MAX_HOUSES = 5
# 首页房屋数据的Redis缓存时间，单位：秒
HOME_PAGE_DATA_REDIS_EXPIRES = 7200

HOUSE_DETAIL_REDIS_EXPIRE_SECOND = 7200
