# backend/services/sms_service.py
import os
import logging
import requests
import json
import time
import hashlib

logger = logging.getLogger(__name__)

def send_payment_success_sms(phone_number, order_no):
    """
    发送支付成功短信 (国阳云 / 通用HTTP接口版)
    """
    if not phone_number:
        logger.warning(f"订单 {order_no} 无手机号，跳过短信")
        return

    # 从环境变量读取
    app_key = os.getenv('SMS_APP_KEY')
    app_secret = os.getenv('SMS_APP_SECRET')
    api_url = os.getenv('SMS_API_URL', 'http://api.guoyangyun.com/api/sms/smsoto.htm') # ⚠️ 请务必确认此URL
    sign_name = os.getenv('SMS_SIGN_NAME', '')

    if not app_key or not app_secret:
        logger.error("❌ 短信配置缺失 (APP_KEY/SECRET)")
        return

    # 构造短信内容
    # 假设不需要申请模板，直接发内容 (如果是营销短信通常需要审核模板)
    content = f"【{sign_name}】您已成功下单，订单号 {str(order_no)[-6:]}，请前往用户中心查看详情。"

    try:
        # --- 构造通用请求参数 ---
        # 注意：不同服务商参数名可能不同 (mobile/phone, content/text, appkey/username)
        # 这里使用最常见的参数命名，如果发不出去，请发给我国阳云的"接口文档"截图
        params = {
            "appkey": app_key,
            "appsecret": app_secret, # 有些接口需要 md5(appsecret + timestamp)
            "mobile": phone_number,
            "content": content
        }

        # 发送请求
        logger.info(f"正在发送短信到 {phone_number}...")
        resp = requests.post(api_url, data=params, timeout=10)
        
        # 记录结果
        logger.info(f"短信接口返回: {resp.text}")

        # 简单判断成功 (通常返回 code: 0 或 200)
        if resp.status_code == 200 and ('0' in resp.text or 'success' in resp.text.lower()):
            logger.info(f"✅ 短信发送成功")
        else:
            logger.error(f"❌ 短信发送失败: {resp.text}")

    except Exception as e:
        logger.error(f"❌ 短信服务异常: {e}")