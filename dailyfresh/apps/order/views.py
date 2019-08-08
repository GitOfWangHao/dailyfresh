from django.shortcuts import render, redirect
from django.views.generic import View
from django.core.urlresolvers import reverse
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django_redis import get_redis_connection
from django.db import transaction
from datetime import datetime
import time

from goods.models import GoodsSKU
from user.models import Address
from order.models import OrderInfo, OrderGoods
from utils.pay.alipay import alipay_trade_page, alipay_trade_query

from utils.mixin import LoginRequiredMixin
# Create your views here.


# /order/place
class OrderPlaceView(LoginRequiredMixin, View):
    """订单提交显示"""

    def post(self, request):
        """提交订单显示"""
        # 获取用户
        user = request.user
        # 获取订单商品id
        sku_ids = request.POST.getlist('sku_ids')

        # 参数校验
        if not sku_ids:
            # 数据为空，返回订单页
            return redirect(reverse('cart：show'))
        # 连接缓存数据库，获取购物车记录
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        # 返回的商品集合，商品总件数，总价格
        skus = []
        total_count = 0
        total_amount = 0

        for sku_id in sku_ids:
            # 获取用户商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 读取购物车中商品数量
            count = con.hget(cart_key, sku_id)
            # 商品小计
            amount = sku.price * int(count)
            # 动态将商品添加count amount 属性
            sku.count =count
            sku.amount = amount
            skus.append(sku)
            # 累加商品的总价格和数量
            total_count += int(count)
            total_amount += amount
        # 运费，实际中由其他子系统计算得出
        transit_price = 10

        # 实付款，总价
        total_pay = total_amount + transit_price

        # 获取用户所有地址
        addrs = Address.objects.filter(user=user)

        # 存储用户订单商品id [1,2]
        sku_ids = ','.join(sku_ids)
        # 组织上下文
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_amount': total_amount,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'nginx_url': settings.FDFS_NGINX_URL,
            'sku_ids': sku_ids,
        }

        return render(request, 'place_order.html', context)


# /order/commit   地址id，支付方式id， 商品id
class OrderCommitView(View):
    """订单创建--悲观锁"""
    @transaction.atomic  # 装饰方法，对函数中的sql操作都封装在一个事物中
    def post(self, request):
        """订单创建"""
        # 判断用户是否登陆
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        # 获取数据
        sku_ids = request.POST.get('sku_ids')  # 商品id ，字符串 1，2
        pay_method = request.POST.get('pay_method')
        addr_id = request.POST.get('addr_id')

        # 校验参数
        if not all([sku_ids, pay_method, addr_id]):
            # print(sku_ids+':'+pay_method+':'+addr_id)
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        if pay_method not in OrderInfo.PAY_METHOD.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})

        # todo:创建订单，组织参数
        # 订单id  20191111000001（时间）+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)  # 主键
        transit_price = 10
        total_count = 0
        total_price = 0
        # 建立sql事务中的保存点，以便后续操作失败回滚
        save_id = transaction.savepoint()
        try:
            # todo:向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price,
            )

            # todo:有几个商品就向df_order_goods添加几条数据
            # 将获得的商品id字符串，转化成id列表
            sku_ids = sku_ids.split(',')
            # 连接缓存数据库，获取购物车记录
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            for sku_id in sku_ids:
                try:
                    # 悲观锁，解决sql并发
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # sql数据库操作回滚
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                # 商品数量
                count = con.hget(cart_key, sku_id)
                # todo:判断商品库存
                if int(count) > sku.stock:
                    # sql数据库操作回滚
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 6, 'errmsg': '商品库库存不足'})

                # todo:向df_order_goods创建一条记录
                OrderGoods.objects.create(
                    order=order,
                    sku=sku,
                    count=count,
                    price=sku.price,
                )
                # todo：更商品新库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # 总数量和总价格
                amount = sku.price*int(count)
                total_count += int(count)
                total_price += amount

            # todo:更新订单记录中的total_count，total_count
            order.total_count = total_count
            order.total_price = total_price + order.transit_price
            order.save()
        except Exception as e:
            # sql数据库操作回滚
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
        # 提交，保存事务
        transaction.savepoint_commit(save_id)
        # todo:清除购物车中已购买商品信息
        con.hdel(cart_key, *sku_ids)  # *list[]----拆包，把数据元素一个一个拿出来

        return JsonResponse({'res': 5, 'message': '创建成功'})


# /order/pay 收款，返回支付宝支付地址
class OrderPayView(View):
    """订单支付"""
    def post(self, request):
        """订单支付---支付宝"""
        # 用户是否登陆
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        # 接受参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单编号'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1,)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 业务处理：使用 sdk 调用支付宝接口
        # todo:让支付宝帮收钱，发金额，订单号等给支付宝，支付宝返回链接引导用户支付
        alipay_response = alipay_trade_page(order)
        if alipay_response is None:
            return JsonResponse({'res': 4, 'errmsg': '与支付宝对接错误'})
        # 返回应答
        # print(str(order.total_price)+':'+order.order_id)
        return JsonResponse({'res': 3, 'pay_url': alipay_response})


# /order/check
class CheckPayView(View):
    """检查支付是否成功"""
    def post(self, request):
        """检查支付是否成功"""
        # 用户是否登陆
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        # 接受参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单编号'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1, )
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 不停的查询，直到支付成功或失败
        while True:

            # todo:支付宝支付结果查询
            # 支付宝返回的查询结果
            response = alipay_trade_query(order)
            if response is None:
                return JsonResponse({'res': 4, 'errmsg': '与支付宝对接错误'})

            # 返回值
            # code: 10000  # 接口调用成功
            # msg: Success
            # buyer_logon_id: rlf ** * @ sandbox.com
            # buyer_pay_amount: 0.00
            # buyer_user_id: 2088102179299453
            # buyer_user_type: PRIVATE
            # invoice_amount: 0.00
            # out_trade_no: 201908061630378  #自己传入的订单id
            # point_amount: 0.00
            # receipt_amount: 0.00
            # send_pay_date: 2019 - 0
            # 8 - 06
            # 16: 31:15
            # total_amount: 39.90
            # trade_no: 2019080622001499451000022039  # 支付宝交易id
            # trade_status: TRADE_SUCCESS  # 交易状态

            # 如果调用业务成功,且支付成功
            if response.code == '10000' and response.trade_status == 'TRADE_SUCCESS':
                # 获取支付宝交易号
                trade_no = response.trade_no
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                return JsonResponse({'res': 3, 'message': '支付成功'})

            elif response.code == '40004' or (response.code == '10000' and response.trade_status == 'WAIT_BUYER_PAY'):
                # 业务还为调用成功但可能会成功或调用业务成功,等待支付成功
                time.sleep(5)
                continue

            else:
                # 支付出错
                return JsonResponse({'res': 5, 'message': '支付出错'})


# /order/comment
class OrderCommentView(View):
    """订单评价"""
    def get(self, request, order_id):
        """通过订单支付页跳转过来评论"""
        # 用户是否登陆
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return redirect(reverse('user:order'))

        # 校验参数
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=4, )
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        order_skus = OrderGoods.objects.filter(order=order)
        for order_sku in order_skus:
            # 计算小计
            amount = order_sku.price*order_sku.count
            # 动态添加属性
            order_sku.amount = amount

        # 动态添加属性
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
        order.order_skus = order_skus

        return render(request, 'order_comment.html', {'order': order, 'nginx_url': settings.FDFS_NGINX_URL})

    def post(self, request, order_id):
        """订单评论提交ajax"""
        # 用户是否登陆
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        # 订单商品ID，评论
        order_goods_id = request.POST.get('order_goods_id')
        comment_text = request.POST.get('comment')

        # 校验参数
        if not order_goods_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单商品编号'})

        if not comment_text:
            return JsonResponse({'res': 2, 'errmsg': '评论不能呢个为空'})

        try:
            order_goods = OrderGoods.objects.get(id=order_goods_id)
        except OrderGoods.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '该订单商品不存在'})

        # 评论提交

        order_goods.comment = comment_text
        order_goods.save()

        # 获取商品所在的订单
        try:
            order = OrderInfo.objects.get(order_id=order_id)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 5, 'errmsg': '该商品订单不存在'})

        order_skus = OrderGoods.objects.filter(order=order)

        order_is_commentted = True

        for order_sku in order_skus:
            if order_sku.comment == 'False':
                order_is_commentted = False
                break
        if order_is_commentted is True:
            order.order_status = 5
            order.save()

        return redirect(reverse('user:order', kwargs={'page': 1}))



class OrderCommitView2(View):
    """订单创建--乐观锁"""
    def post(self, request):
        """订单创建"""
        # 判断用户是否登陆
        user = request.user
        # 未登陆无法操作
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})
        # 获取数据
        sku_ids = request.POST.get('sku_ids')  # 商品id ，字符串 1，2
        pay_method = request.POST.get('pay_method')
        addr_id = request.POST.get('addr_id')

        # 校验参数
        if not all([sku_ids, pay_method, addr_id]):
            # print(sku_ids+':'+pay_method+':'+addr_id)
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        if pay_method not in OrderInfo.PAY_METHOD.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})

        # todo:创建订单，组织参数
        # 订单id  20191111000001（时间）+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)  # 主键
        transit_price = 10
        total_count = 0
        total_price = 0
        # 建立sql事务中的保存点，以便后续操作失败回滚
        save_id = transaction.savepoint()
        try:
            # todo:向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price,
            )

            # todo:有几个商品就向df_order_goods添加几条数据
            # 将获得的商品id字符串，转化成id列表
            sku_ids = sku_ids.split(',')
            # 连接缓存数据库，获取购物车记录
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            for sku_id in sku_ids:
                for i in range[3]:
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # sql数据库操作回滚
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                    # 商品数量
                    count = con.hget(cart_key, sku_id)
                    # todo:判断商品库存
                    if int(count) > sku.stock:
                        # sql数据库操作回滚
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errmsg': '商品库库存不足'})

                    # todo:向df_order_goods创建一条记录
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price,
                    )
                    # todo：更商品新库存和销量----使用悲观锁解决并发问题
                    origin_stock = sku.stock
                    new_stock = origin_stock - int(count)
                    new_sales = sku.sales + origin_stock
                    # 返回受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        # sql数据库操作回滚
                        if i == 2:  # 尝试三次都失败，则真的失败
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
                        continue

                    # 总数量和总价格
                    amount = sku.price*int(count)
                    total_count += int(count)
                    total_price += amount

                    # 修改数据库成功，跳出循环
                    break

            # todo:更新订单记录中的total_count，total_count
            order.total_count = total_count
            order.total_price = total_price + order.transit_price
            order.save()
        except Exception as e:
            # sql数据库操作回滚
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
        # 提交，保存事务
        transaction.savepoint_commit(save_id)
        # todo:清除购物车中已购买商品信息
        con.hdel(cart_key, *sku_ids)  # *list[]----拆包，把数据元素一个一个拿出来

        return JsonResponse({'res': 5, 'message': '创建成功'})