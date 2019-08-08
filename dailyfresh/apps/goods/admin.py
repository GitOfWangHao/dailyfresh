from django.contrib import admin
from goods.models import GoodsType,  IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from django.core.cache import cache

# Register your models here.


class BaseModelAdmin(admin.ModelAdmin):
    """用于后台管理页面更新首页数据时重新生成静态首页"""
    def save_model(self, request, obj, form, change):
        """新增或更新表中数据时调用"""
        super().save_model(request, obj, form, change)  # 继承父类原有操作
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()  # 生成静态页面

        # 首页数据改变时，清除首页数据缓存, 在请求页重新请求并设置缓存
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """删除表中数据时调用"""
        super().delete_model(request, obj)  # 继承父类原有操作
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()  # 生成静态页面

        # 首页数据改变时，清除首页数据缓存, 在请求页重新请求并设置缓存
        cache.delete('index_page_data')

class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


class GoodsTypeAdmin(BaseModelAdmin):
    pass


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexGoodsBanner, IndexTypeGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)
admin.site.register(GoodsSKU)
