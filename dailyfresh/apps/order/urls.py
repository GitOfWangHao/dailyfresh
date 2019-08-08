
from django.conf.urls import url
from order.views import OrderPlaceView, OrderCommitView, OrderPayView, CheckPayView, OrderCommentView

urlpatterns = [
    url(r'^place$', OrderPlaceView.as_view(), name='place'),  # 订单提交显示
    url(r'^commit$', OrderCommitView.as_view(), name='commit'),  # 订单生成
    url(r'^pay$', OrderPayView.as_view(), name='pay'),  # 生成支付宝支付链接
    url(r'^check$', CheckPayView.as_view(), name='check'),  # 查询订单的支付状态
    url(r'^comment/(?P<order_id>\d+)$', OrderCommentView.as_view(), name='comment'),  # 订单评价
]
