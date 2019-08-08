
from django.conf.urls import url
from cart.views import CartAddView, CartInfoView, CartUpdateView, CartDeleteView

urlpatterns = [
    url(r'^add$', CartAddView.as_view(), name='add'),  # 购物车记录添加
    url(r'^$', CartInfoView.as_view(), name='show'),  # 显示购物车内容
    url(r'^update$', CartUpdateView.as_view(), name='update'),  # 更新购物车数据
    url(r'^delete$', CartDeleteView.as_view(), name='delete'),  # 删除购物车记录
]
