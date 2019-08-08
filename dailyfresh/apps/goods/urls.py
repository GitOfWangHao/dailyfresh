
from django.conf.urls import url
from goods.views import IndexView, DetailView, ListView

urlpatterns = [
        url(r'^index$', IndexView.as_view(), name='index'),  # 显示有页商品页
        url(r'^goods/(?P<goods_id>\d+)$', DetailView.as_view(), name='detail'),  # 显示商品详细信息
        url(r'^list/(?P<type_id>\d+)/(?P<page>\d+)$', ListView.as_view(), name='list')  # 商品列表页
]
