from django.contrib.auth.decorators import login_required  # 使用django提供的登陆验证装饰器，验证用户是否已经登陆


class LoginRequiredMixin(object):
    """实现登陆验证的类，需要每一个视图类继承"""
    @classmethod
    def as_view(cls, **initkwargs):
        # 调用父类静态方法 View 类
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)  # 调用 view类中的as_view！！！ 值的探究
        return login_required(view)
