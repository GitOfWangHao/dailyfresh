from django.db import models


class BaseModel(models.Model):
    """模型抽象类，让所有模型都继承属性"""
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    up_time = models.DateTimeField(auto_now=True, verbose_name='修改时间')
    id_delete = models.BooleanField(default=False, verbose_name='删除标记')

    class Meta:
        # 说明是一个抽象类型
        abstract = True
