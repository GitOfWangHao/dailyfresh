from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from order.models import OrderGoods
from django_redis import get_redis_connection
from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator

# Create your views here.


# 返回首页 /index
class IndexView(View):
    """首页视图类"""

    def get(self, request):
        """get请求返回首页"""
        # 获取缓存
        content = cache.get('index_page_data')
        if content is None:

            # 如果没有缓存数据
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
                'nginx_url': settings.FDFS_NGINX_URL,
            }

            # 设置页面数据库查询缓存
            cache.set('index_page_data', content, 3600)

        # 获取用户购物车中商品的数量
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登陆
            con = get_redis_connection('default')
            cart_key = 'cart_%s' % user.id
            cart_count = con.hlen(cart_key)

        # 更新，不存在就添加
        content.update(cart_count=cart_count)

        return render(request, 'index.html', content)


# goods/商品id
class DetailView(View):
    """返回商品详情"""
    def get(self, request, goods_id):
        """返回商品信息"""
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))
        # 获取商品的全部种类信息
        types = GoodsType.objects.all()

        # 获取评论信息,排除没有评论订单
        sku_order = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 获取新品推荐,从sku中获取对应类型的商品，并按照时间降序,取前两个
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取同一个SPU其他规格的商品信息
        same_spu_sku = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)
        # 获取用户购物车中商品的数量
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登陆
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)

            # 添加用户浏览记录
            con = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 移除当前商品的商品的浏览记录
            con.lrem(history_key, 0, goods_id)
            # 添加商品到浏览记录
            con.lpush(history_key, goods_id)
            # 只保留最新的5条浏览记录
            con.ltrim(history_key, 0, 5)

        # 组织上下文
        context = {
            'sku': sku,
            'types': types,
            'sku_order': sku_order,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'same_spu_sku': same_spu_sku,
            'nginx_url': settings.FDFS_NGINX_URL,
        }

        return render(request, 'detail.html', context)


# goods/商品种类id/页码？排序方式
class ListView(View):
    """列表页"""
    def get(self, request, type_id, page):
        """列表页"""
        # 获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()
        # 获取排序方式
        # sort = default, 默认方式按id排
        # sort = price, 按价格排
        # sort = hot, 按销量sales排
        sort = request.GET.get('sort')

        # 获取分类商品信息
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 对数据进行分页
        paginator = Paginator(skus, 1)

        # 判断传过来的page数据
        try:
            page = int(page)
        except Exception as e:
            page = 1

        # 传入的page大于最大值
        if page > paginator.num_pages:
            page = 1
        # 获取page页数据
        page_skus = paginator.page(page)

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

        # 获取新品推荐,从sku中获取对应类型的商品，并按照时间降序,取前两个
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]
        # 获取用户购物车中商品的数量
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登陆
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)

        context = {
            'type': type,
            'types': types,
            'page_skus': page_skus,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'nginx_url': settings.FDFS_NGINX_URL,
            'sort': sort,
            'pages': pages,
        }

        return render(request, 'list.html', context)

