# backend/routes/pay.py
import os
import time
import json
import logging
import traceback
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity 

from extensions import db
from models.user import User
# from models.order import Order # 建议后续开启

# --- 支付 SDK ---
from wechatpayv3 import WeChatPay, WeChatPayType
from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePrecreateModel import AlipayTradePrecreateModel
from alipay.aop.api.request.AlipayTradePrecreateRequest import AlipayTradePrecreateRequest

# --- 短信服务 ---
from services.sms_service import send_payment_success_sms

pay_bp = Blueprint('pay', __name__, url_prefix='/api/pay')
logger = logging.getLogger(__name__)

# ==================== 支付宝客户端 (密钥模式) ====================
def get_alipay_client():
    """从环境变量直接读取密钥字符串初始化"""
    try:
        app_id = os.getenv('ALIPAY_APPID')
        private_key = os.getenv('ALIPAY_PRIVATE_KEY')
        public_key = os.getenv('ALIPAY_PUBLIC_KEY')

        if not all([app_id, private_key, public_key]):
            logger.error("支付宝配置缺失: 请检查 .env 中的 APPID 和 KEY")
            return None

        config = AlipayClientConfig()
        config.app_id = app_id
        # 直接使用字符串密钥
        config.app_private_key = private_key
        config.alipay_public_key = public_key
        
        config.endpoint = os.getenv('ALIPAY_GATEWAY', "https://openapi.alipay.com/gateway.do")
        config.sign_type = "RSA2"
        
        return DefaultAlipayClient(config_config=config)
    except Exception as e:
        logger.error(f"支付宝初始化失败: {e}")
        return None

# ==================== 微信客户端 (保持不变) ====================
def get_wxpay_client():
    try:
        private_key_path = os.getenv('WX_PRIVATE_KEY_PATH', './cert/apiclient_key.pem')
        if not os.path.exists(private_key_path): return None
        with open(private_key_path, 'r') as f: private_key = f.read()
        return WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=os.getenv('WX_MCHID'),
            private_key=private_key,
            cert_serial_no=os.getenv('WX_CERT_SERIAL_NO'),
            apiv3_key=os.getenv('WX_APIV3_KEY'),
            appid=os.getenv('WX_APPID'),
            notify_url=os.getenv('WX_NOTIFY_URL'),
            cert_dir='./cert',
            logger=logger
        )
    except: return None

# ==================== 下单接口 ====================
@pay_bp.route('/prepare', methods=['POST'])
@jwt_required(optional=True) 
def prepare_pay():
    data = request.get_json() or {}
    amount_yuan = data.get('amount', 0)
    channel = data.get('channel', 'wechat')
    user_id = get_jwt_identity()

    if amount_yuan <= 0: return jsonify({'msg': '金额异常'}), 400

    out_trade_no = f"ORD{int(time.time() * 1000)}"
    # 构造描述，防止过长
    items = data.get('items', [])
    desc = f"GoAbroady-{items[0]['title']}" if items else "GoAbroady Service"
    if len(desc) > 100: desc = desc[:97] + "..."

    # 1. 尝试查找用户手机号 (用于调试日志，实际发送在回调里)
    if user_id:
        user = User.query.get(user_id)
        if user: logger.info(f"当前下单用户: {user.username}, 手机: {user.phone}")

    # === 支付宝逻辑 ===
    if channel == 'alipay':
        client = get_alipay_client()
        if not client: return jsonify({'msg': '支付宝配置错误'}), 500
        
        try:
            model = AlipayTradePrecreateModel()
            model.out_trade_no = out_trade_no
            model.total_amount = str(amount_yuan)
            model.subject = desc
            
            req = AlipayTradePrecreateRequest(biz_model=model)
            # 这里的 notify_url 会优先于应用配置
            req.notify_url = os.getenv('ALIPAY_NOTIFY_URL')
            
            resp_str = client.execute(req)
            resp = json.loads(resp_str)
            alipay_resp = resp.get('alipay_trade_precreate_response', {})
            
            if alipay_resp.get('code') == '10000':
                return jsonify({
                    'code_url': alipay_resp.get('qr_code'),
                    'order_no': out_trade_no,
                    'msg': '支付宝下单成功'
                })
            else:
                logger.error(f"支付宝报错: {alipay_resp.get('sub_msg')}")
                return jsonify({'msg': '支付宝下单失败', 'detail': alipay_resp}), 500
        except Exception as e:
            logger.error(f"支付宝异常: {e}")
            return jsonify({'msg': '系统支付异常'}), 500

    # === 微信逻辑 (原有) ===
    elif channel == 'wechat':
        wxpay = get_wxpay_client()
        if not wxpay: return jsonify({'msg': '微信配置错误'}), 500
        try:
            code, result = wxpay.pay(
                description=desc,
                out_trade_no=out_trade_no,
                amount={'total': int(amount_yuan * 100)},
                pay_type=WeChatPayType.NATIVE
            )
            if isinstance(result, str): result = json.loads(result) # 兼容处理
            
            if code in [200, 202] and result.get('code_url'):
                return jsonify({
                    'code_url': result['code_url'],
                    'order_no': out_trade_no,
                    'msg': '微信下单成功'
                })
            return jsonify({'msg': '微信下单失败', 'detail': result}), 500
        except Exception as e:
            logger.error(f"微信异常: {e}")
            return jsonify({'msg': '系统异常'}), 500

    return jsonify({'msg': '不支持的渠道'}), 400

# ==================== 回调通知 ====================
@pay_bp.route('/notify/alipay', methods=['POST'])
def notify_alipay():
    """ 支付宝回调 + 触发短信 """
    try:
        data = request.form.to_dict()
        trade_status = data.get('trade_status')
        out_trade_no = data.get('out_trade_no')

        # 验签逻辑 (建议加上 client.verify(data, sign))
        
        if trade_status in ['TRADE_SUCCESS', 'TRADE_FINISHED']:
            logger.info(f"💰 支付宝到账: {out_trade_no}")
            
            # TODO: 这里应该更新订单状态为 PAID
            
            # 🚀 尝试发送短信
            # 因为是异步回调，我们这里没有 user_id，需要查库
            # 演示代码：假设我们通过 out_trade_no 查到了用户手机号
            # order = Order.query.filter_by(out_trade_no=out_trade_no).first()
            # if order and order.user and order.user.phone:
            #     send_payment_success_sms(order.user.phone, out_trade_no)
            
            return 'success'
    except Exception as e:
        logger.error(f"回调处理失败: {e}")
    return 'fail'

# 微信回调保持原样...