# backend/services/sms_service.py
import os
import logging
import requests
import urllib.parse

logger = logging.getLogger(__name__)

def send_payment_success_sms(phone_number, order_no, product_name="留学服务"):
    """
    发送支付成功短信 (国阳云接口)
    """
    if not phone_number:
        logger.warning(f"⚠️ [短信] 订单 {order_no} 无手机号，跳过发送")
        return

    # 1. 从环境变量读取配置
    # 注意：国阳云通常使用 username/password 或 appkey/secret，请根据你实际拿到的参数调整
    # 这里根据你提供的 .env 示例使用 appkey/appsecret
    gateway = os.getenv('SMS_API_URL', 'http://api.guoyangyun.com/api/sms/smsoto.htm')
    app_key = os.getenv('SMS_APP_KEY')
    app_secret = os.getenv('SMS_APP_SECRET')
    sign_name = os.getenv('SMS_SIGN_NAME', 'GoAbroady')

    if not app_key or not app_secret:
        logger.error("❌ [短信] 配置缺失: 请检查 SMS_APP_KEY 和 SMS_APP_SECRET")
        return

    # 2. 构造短信内容
    # 示例：【GoAbroady】您购买的“留学咨询”已支付成功，订单号123456，请登录查看。
    content = f"【{sign_name}】您购买的“{product_name}”已支付成功，订单号{str(order_no)[-6:]}，请登录用户中心查看详情。"

    try:
        # 3. 构造请求参数 (国阳云标准参数)
        params = {
            "appkey": app_key,
            "appsecret": app_secret,
            "mobile": phone_number,
            "content": content
        }

        # 4. 发送请求
        logger.info(f"📡 [短信] 正在发送给 {phone_number} ...")
        resp = requests.post(gateway, data=params, timeout=10)
        
        # 5. 处理响应
        # 国阳云成功通常返回 code 200 且 body 包含 "0" 或 "success"
        resp_text = resp.text
        if resp.status_code == 200 and ('"code":"0"' in resp_text or '"code":0' in resp_text):
            logger.info(f"✅ [短信] 发送成功: {resp_text}")
            return True
        else:
            logger.error(f"❌ [短信] 服务商报错: {resp_text}")
            return False

    except Exception as e:
        logger.error(f"❌ [短信] 请求异常: {str(e)}")
        return False