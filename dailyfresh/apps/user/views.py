from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse   # 重定向页面，需要使用反向解析
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.views.generic import View

from celery_tasks.tasks import send_register_active_email
from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from utils.mixin import LoginRequiredMixin  # 登陆验证装饰器
from django_redis import get_redis_connection

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer  # 使用itsdangerous进行激活加密
from itsdangerous import SignatureExpired
import re  # 正则表达式

# Create your views here.


class RegisterView(View):
    """注册视图类，可以自动调用get post 请求对应处理"""

    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """注册处理"""
        # 获取数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 校验
        if not all([username, password, email]):
            # 有数据惟恐
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意用户协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)  # 如果存在则返回数据，否则报错
        except User.DoesNotExist:
            # 用户名不存在
            user = None

        # 用户名以存在
        if user:
            return render(request, 'register.html', {'errmsg': '用户名以存在'})

        # 业务处理，进行用户注册
        user = User.objects.create_user(username, email, password)  # 使用系统提供的创建保存数据方法
        user.is_active = 0  # 未注册
        user.save()

        # 进行激活
        # itsdangerous 产生激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)  # 密钥，过期时间
        info = {'confirm': user.id}   # 要加密的信息
        token = serializer .dumps(info)  # byte,要解码 # 对信息加密产生token
        token = token.decode()  # 默认utf8解码

        send_register_active_email.delay(email, username, token)

        return redirect(reverse('goods:index'))  # 配置namespace:name


class ActiveView(View):
    """激活处理"""

    def get(self, request, token):
        """验证"""
        serializer = Serializer(settings.SECRET_KEY, 3600)  # 密钥，过期时间
        try:   # 验证token，且未过期，激活用户
            res = serializer.loads(token)
            user_id = res['confirm']
            user = User.objects.get(id=user_id)
            user.is_active = 1  # 激活用户
            user.save()

            # 激活成功
            return redirect(reverse('user:login'))
        except SignatureExpired:  # 过期
            return HttpResponse("激活链接已过期")


class LoginView(View):
    """登陆"""

    def get(self, request):
        """登陆页面"""
        # 判断是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        """登陆处理"""

        # 获取数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 验证数据是否为空
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不能为空'})

        # ----------------django提供的认证工具！！！---------------
        # 校验数据,由于用户类使用的django提供的AbstractUser,所以用户的登陆验证使用django提供authenticate
        user = authenticate(username=username, password=password)
        if user is not None:
            # 登陆成功
            if user.is_active:
                # 用户已激活
                # 记录用户的登陆状态,同样使用django提供的记录用户登陆状态的login，应该会在浏览器写一些cookie
                login(request, user)

                # 获取登陆后要跳转的地址
                # 如果next返回值不是None则，接受返回值，否则接受自定义值
                next_url = request.GET.get('next', reverse('goods:index'))
                # 登陆成功，跳转next_url
                response = redirect(next_url)  # 得到的是一个Heepresponseredirect对象，可以设置cookie

                # 校验是否记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username', username, 3600)
                else:
                    response.delete_cookie('username')

                return response

            else:
                return render(request, 'login.html', {'errmsg': '账户未激活'})
        else:
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})


# user/logout
class LogoutView(View):
    """用户退出登陆页面"""
    def get(self, request):
        """调用django提供退出登陆方法，清除之前login设置的session，cookie"""
        logout(request)
        # 跳转首页
        return redirect(reverse("goods:index"))


# ------用户中心相关页面
# user/
# 关于LoginRequiredMixin，调用as_view方法时，先到LoginRequiredMixin中找
class UserInfoView(LoginRequiredMixin, View):
    """用户中心--信息页"""

    def get(self, request):
        # 用于标识当前页面
        # page:'user'

        # Django 会给request添加一个user 属性 request.user
        # 如果request.user，通过查询返回值可以判断是否已登陆
        # 如果未登陆返回值是AnonymousUser实例
        # 登陆返回User实例 request.user.is_authenticated 判断是否已登陆

        # 获取用户个人信息
        user = request.user
        address = Address.objects.get_default_address(user)
        # 获取用户浏览记录
        # 在redis中,以list格式存储
        con = get_redis_connection('default')  # 使用django-redis默认连接redis方法
        history_key = 'history_%d' % user.id  # 用户浏览数据键的名

        # 获取最近浏览的5个商品信息
        sku_ids = con.lrange(history_key, 0, 4)  # 返回浏览商品的sku ID 列表

        # 从数据库读取商品信息
        goods_list = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_list.append(goods)

        # 组织上下文
        context = {'page': 'user',
                   'address': address,
                   'goods_list': goods_list,
                   'nginx_url': settings.FDFS_NGINX_URL,
                   }

        return render(request, 'user_center_info.html', context)


# user/order
class UserOrderView(LoginRequiredMixin, View):
    """用户中心--订单页"""

    def get(self, request, page):
        # 展示用户所有已提交订单
        # page:'order'
        # 读取用户信息
        user = request.user

        # 获取该用户所有订单信息
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        for order in orders:
            # 单个订单，得到所有订单商品
            order_skus = OrderGoods.objects.filter(order=order)
            # 计算每个商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.price*order_sku.count
                # 动态添加属性amount,保存小计
                order_sku.amount = amount

            # 动态添加属性，保存订单支付状态
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态添加属性，保存订单的商品信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 1)
        # 判断传过来的page数据
        try:
            page = int(page)
        except Exception as e:
            page = 1

        # 传入的page大于最大值
        if page > paginator.num_pages:
            page = 1
        # 获取page页数据
        order_pages = paginator.page(page)

        # 进行页码控制，最多只显示5页
        # 1.总页数小于5，显示所有页码
        # 2.如果当前是前3页，显示1-5页
        # 3。如果是后3页，显示后5页
        # 4.其他情况，显示前2页，当前页，后2页
        num_pages = paginator.num_pages  # 总页数
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 上下文
        context = {
            'order_pages': order_pages,
            'pages': pages,
            'page': 'order',
            'nginx_url': settings.FDFS_NGINX_URL,
        }
        # 获取用户订单信息
        return render(request, 'user_center_order.html', context)


# user/address
class AddressView(LoginRequiredMixin, View):
    """用户中心--地址页"""

    def get(self, request):
        """显示默认数据页面"""
        # 用于标识当前页面
        # page:'address'

        # 获取已经登陆的用户
        user = request.user

        # 判断是否有默认地址
        address = Address.objects.get_default_address(user)

        # 获取用户默认地址
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        """用于提交修改、添加的地址"""

        # 数据获取
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 数据校验
        if not all([receiver, addr, phone]):  # 邮编可以为空
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})

        if re.match(r'^1[3|5|7|8][0-9]{7}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机号格式不正确'})

        # 业务处理：地址添加
        # 获取已经登陆的用户
        user = request.user

        # 判断是否有默认地址
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True

        # 创建新的收货地址，写入数据库
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default,)

        # 返回应答，刷新地址页面
        return redirect(reverse('user:address'))

