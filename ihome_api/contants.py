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
