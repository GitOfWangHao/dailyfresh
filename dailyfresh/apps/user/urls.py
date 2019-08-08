from django.conf.urls import url
from user.views import RegisterView, ActiveView, LoginView, LogoutView, UserInfoView, UserOrderView, AddressView


urlpatterns = [
    url(r'^register$', RegisterView.as_view(), name='register'),  # 注册页面
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),  # 激活页面
    url(r'^login$', LoginView.as_view(), name='login'),  # 登陆页面
    url(r'^logout', LogoutView.as_view(), name='logout'),  # 注销用户，推出登陆状态
    url(r'^$', UserInfoView.as_view(), name='user'),  # 用户信息页
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'),  # 用户订单页
    url(r'^address', AddressView.as_view(), name='address'),  # 用户地址页

]
