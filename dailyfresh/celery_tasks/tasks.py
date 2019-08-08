from celery import Celery
from django.core.mail import send_mail
from django.conf import settings
from django.template import loader

import os
import django

# 完成异步任务的建立与中间者broker的创建

# 创建celery实例对象
apps = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/8')

# worker 页需要配置的
# # 由于任务执行只启动当前py文件，所以需要依赖的系统设置要引入
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from utils.mixin import LoginRequiredMixin  # 登陆验证装饰器
# 定义任务函数
@apps.task
def send_register_active_email(to_email, username, token):
    # 发邮件
    subject = '天天生鲜练习'  # 邮件主题
    message = ''  # 邮件内容,文字内容
    from_mail = settings.EMAIL_FROM  # 发件人
    recipient_list = [to_email]  # 收件人列表
    # 发送网页内容
    html_message = '<h1>%s,欢迎您成为天天生鲜会员</h1><br/>请点击点击链接激活<br/>' \
                   '<a href = "%s/user/active/%s">' \
                   '%s/user/active/%s</a>' % (username, settings.VM_IP, token, settings.VM_IP, token)

    send_mail(subject, message, from_mail, recipient_list, html_message=html_message)
    # 返回应答, 跳转到首页

# 定义任务函数
@apps.task
def generate_static_index_html():
    """生成静态index页"""
    # 获取商品的种类信息
    types = GoodsType.objects.all()
    # 获取首页轮播商品信息
    goods_banner = IndexGoodsBanner.objects.all().order_by('index')
    # 获取首页促销活动信息
    promotion_banner = IndexPromotionBanner.objects.all().order_by('index')
    # 获取首页分类商品展示信息

    for type in types:
        # 获取首页type种类的图片展示信息
        image_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
        # 获取首页type种类的文字展示信息
        title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')

        # python 可以动态的给对象添加属性
        type.image_banner = image_banner
        type.title_banner = title_banner

    content = {
        'types': types,
        'goods_banner': goods_banner,
        'promotion_banner': promotion_banner,
        'nginx_url': settings.FDFS_NGINX_URL
    }

    # 使用模板生成模板文件----最原始的方法
    # 1.加载模板文件，生成模板对象
    temp = loader.get_template('static_index.html')
    # 2.渲染
    static_index_html = temp.render(content)

    # 保存路径 static/index.html
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')

    # 保存文件
    with open(save_path, 'w') as f:
        f.write(static_index_html)
