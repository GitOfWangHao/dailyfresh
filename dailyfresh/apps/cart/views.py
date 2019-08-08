from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from django.conf import settings
# Create your views here.


# /cart/add
class CartAddView(View):
    """添加购物车视图"""
    def post(self, request):
        """通过ajax的post方式发送数据"""
        # 1.获取数据
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 2.校验数据
        # 校验数据完整性
        if not all([sku_id, count]):

            return JsonResponse({'res': 1, 'errmsg':'数据不完整'})
        # 校验数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg':'商品数目出错'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 3.业务处理：添加购物车记录
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先尝试获取sku_id 的值，如果没有，hget返回none
        cart_count = con.hget(cart_key, sku_id)
        if cart_count:
            count += int(cart_count)
        # 判断库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        # 设置hash中sku_id的值，如果有就是更新，没有时添加
        con.hset(cart_key, sku_id, count)
        # 统计商品的条目数
        total_count = con.hlen(cart_key)
        # 4.返回数据
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '添加成功'})


# /cart
class CartInfoView(LoginRequiredMixin, View):
    """显示购物车页面"""
    def get(self, request):
        """显示"""
        # 读取用户名
        user = request.user
        # 链接redis数据库
        cart_key = 'cart_%d' % user.id
        con = get_redis_connection('default')
        # 获取数据，{'key':value}
        cart_dict = con.hgetall(cart_key)

        # 商品sku对象字典
        skus = []
        # 购物册总商品件数
        total_count = 0
        # 购物车总价格
        total_amount = 0
        # 便利购物车数据
        for sku_id, count in cart_dict.items():
            sku = GoodsSKU.objects.get(id=sku_id)
            amount = sku.price*int(count)
            # 给sku对象动态添加amout属性，保存商品小计
            sku.amount = amount
            # 给sku对象动态添加count属性，保存商品件数
            sku.count = count
            # 添加
            skus.append(sku)
            # 累加
            total_count += int(count)
            total_amount += amount
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_amount': total_amount,
            'nginx_url': settings.FDFS_NGINX_URL,
        }

        return render(request, 'cart.html', context)


# /cart/update
class CartUpdateView(View):
    """更新购物车商品信息"""
    def post(self, request):
        """通过ajax更新信息"""
        # 1.获取数据
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 2.校验数据
        # 校验数据完整性
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 校验数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 3.业务处理：添加购物车记录
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 判断库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        # 设置hash中sku_id的值，如果有就是更新，没有时添加
        con.hset(cart_key, sku_id, count)

        # 获取购物车中总数量
        total_count = 0
        vals = con.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        # 4.返回数据
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '添加成功'})


# /cart/delete
class CartDeleteView(View):
    """删除购物车商品"""
    def post(self, request):
        # 通过ajax传递数据，post
        # 1.获取数据
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        sku_id = request.POST.get('sku_id')
        # 2.校验数据
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的商品id'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 业务处理，删除数据
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 删除
        con.hdel(cart_key, sku_id)

        # 获取购物车中总数量
        total_count = 0
        vals = con.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res': 3, 'total_count': total_count, 'message': '删除成功'})



