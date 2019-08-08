#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import traceback

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.FileItem import FileItem
from alipay.aop.api.domain.AlipayTradeAppPayModel import AlipayTradeAppPayModel
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.domain.AlipayTradePayModel import AlipayTradePayModel
from alipay.aop.api.domain.GoodsDetail import GoodsDetail
from alipay.aop.api.domain.SettleDetailInfo import SettleDetailInfo
from alipay.aop.api.domain.SettleInfo import SettleInfo
from alipay.aop.api.domain.SubMerchant import SubMerchant
from alipay.aop.api.request.AlipayOfflineMaterialImageUploadRequest import AlipayOfflineMaterialImageUploadRequest
from alipay.aop.api.request.AlipayTradeAppPayRequest import AlipayTradeAppPayRequest
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from alipay.aop.api.request.AlipayTradePayRequest import AlipayTradePayRequest
from alipay.aop.api.response.AlipayOfflineMaterialImageUploadResponse import AlipayOfflineMaterialImageUploadResponse
from alipay.aop.api.response.AlipayTradePayResponse import AlipayTradePayResponse

from alipay.aop.api.response.AlipayTradeQueryResponse import AlipayTradeQueryResponse
from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest

"""
支付宝SDK使用总结：
    1.基础配置：注意事项见 alipay_base_config
    2.业务所需api 导入
        1.明确请求的业务，到 alipay.aop.api.request.下找对应名
        2.请求对象model alipay.aop.api.domain.下找对应名，在大的model下可能参数是符合的在alipay.aop.api.domain.再找
        3.响应参数的处理JASON化，alipay.aop.api.response.下找
    3.业务处理流程
        1.对照接口文档，构造请求对象----针对自己的需求，填写参数，注意必填项
        2.构造的请求,将构造的请求对象填入
        3.client执行请求，执行函数要对照官方JAVA示例选取
        4.对请求结果处理，若是查询，可以用官方的响应处理对结果处理，或直接返回结果
"""

from django.conf import settings

logging.basicConfig(
    # level=logging.INFO,  默认日志打印级别
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s',
    filemode='a',)
logger = logging.getLogger('')


def alipay_base_config():
    """
    设置配置，包括支付宝网关地址、app_id、应用私钥、支付宝公钥等，其他配置值可以查看AlipayClientConfig的定义。
    """

    alipay_client_config = AlipayClientConfig()
    alipay_client_config.server_url = 'https://openapi.alipaydev.com/gateway.do'  # 支付宝网关地址，沙箱的话加dev
    alipay_client_config.app_id = settings.ALIPAY_APP_ID
    # 公钥，私钥要读出来
    with open(settings.MY_PRIVATE_KEY, 'r') as f:
        alipay_client_config.app_private_key = f.read()

    with open(settings.ALIPAY_PUBLIC_KEY, 'r') as f:
        alipay_client_config.alipay_public_key = f.read()
    # 沙箱模式
    alipay_client_config.sandbox_debug = True

    """
    得到客户端对象。
    注意，一个alipay_client_config对象对应一个DefaultAlipayClient，定义DefaultAlipayClient对象后，alipay_client_config不得修改，如果想使用不同的配置，请定义不同的DefaultAlipayClient。
    logger参数用于打印日志，不传则不打印，建议传递。
    """
    client = DefaultAlipayClient(alipay_client_config=alipay_client_config, logger=logger)
    return client


def alipay_trade_page(order):
    """
    页面接口示例：alipay.trade.page.pay,--统一收单下单
    """
    client = alipay_base_config()
    # 对照接口文档，构造请求对象
    model = AlipayTradePagePayModel()
    # 必填
    model.out_trade_no = order.order_id
    model.total_amount = str(order.total_price)
    model.subject = "天天生鲜测试"
    model.product_code = "FAST_INSTANT_TRADE_PAY"
    # 选填中有些必填
    settle_detail_info = SettleDetailInfo()
    settle_detail_info.amount = str(order.total_price)  # 必填
    settle_detail_info.trans_in_type = "userId"   # 必填
    settle_detail_info.trans_in = settings.ALIPAY_UID  # 必填
    settle_detail_infos = list()
    settle_detail_infos.append(settle_detail_info)
    settle_info = SettleInfo()
    settle_info.settle_detail_infos = settle_detail_infos
    model.settle_info = settle_info

    # 与银行有关
    # sub_merchant = SubMerchant()
    # sub_merchant.merchant_id = "2088301300153242"
    # model.sub_merchant = sub_merchant

    request = AlipayTradePagePayRequest(biz_model=model)
    # 得到构造的请求，如果http_method是GET，则是一个带完成请求参数的url，如果http_method是POST，则是一段HTML表单片段
    response = client.page_execute(request, http_method="GET")
    return response
    # print("alipay.trade.page.pay response:" + response)


def alipay_trade_query(order):
    """查询订单结果"""
    client = alipay_base_config()
    # 对照接口文档，构造请求对象
    model = AlipayTradeQueryModel()
    # 通过先前提交的订单号（非支付宝订单号），查询支付结果
    model.out_trade_no = order.order_id
    request = AlipayTradeQueryRequest(biz_model=model)

    response_content = None
    try:
        # 执行请求，返回结果是一个字符串，实际这个值已经够用了
        response_content = client.execute(request)
    except Exception as e:
        print(traceback.format_exc())

    if not response_content:
        print("failed execute")
    else:
        # 将响应结果的字符串数据转化未JSON数据,应该不会再发送请求！！！
        response = AlipayTradeQueryResponse()
        # 解析响应结果
        response.parse_response_content(response_content)
        return response







