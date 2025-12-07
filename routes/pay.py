# backend/routes/pay.py
import os
import time
import json
import logging
import traceback
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity 

from extensions import db
from models.user import User
from models.order import Order 

# --- 支付 SDK ---
from wechatpayv3 import WeChatPay, WeChatPayType
from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePrecreateModel import AlipayTradePrecreateModel
from alipay.aop.api.request.AlipayTradePrecreateRequest import AlipayTradePrecreateRequest
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel

# --- 短信服务 ---
from services.sms_service import send_payment_success_sms

pay_bp = Blueprint('pay', __name__, url_prefix='/api/pay')
logger = logging.getLogger(__name__)

# ==================== 1. 支付宝客户端初始化 ====================
def get_alipay_client():
    try:
        app_id = os.getenv('ALIPAY_APPID')
        private_key = os.getenv('ALIPAY_PRIVATE_KEY')
        public_key = os.getenv('ALIPAY_PUBLIC_KEY')

        if not all([app_id, private_key, public_key]):
            logger.error("支付宝配置缺失")
            return None

        config = AlipayClientConfig()
        config.app_id = app_id
        config.app_private_key = private_key
        config.alipay_public_key = public_key
        config.endpoint = os.getenv('ALIPAY_GATEWAY', "https://openapi.alipay.com/gateway.do")
        config.sign_type = "RSA2"
        
        # 修复点：参数名必须是 alipay_client_config
        return DefaultAlipayClient(alipay_client_config=config)
    except Exception as e:
        logger.error(f"支付宝初始化失败: {e}")
        return None

# ==================== 2. 微信客户端初始化 ====================
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

# ==================== 3. 下单接口 (保存数据库) ====================
@pay_bp.route('/prepare', methods=['POST'])
@jwt_required(optional=True) 
def prepare_pay():
    data = request.get_json() or {}
    amount_yuan = data.get('amount', 0)
    channel = data.get('channel', 'wechat') # alipay 或 wechat
    user_id = get_jwt_identity()

    if amount_yuan <= 0: return jsonify({'msg': '金额异常'}), 400

    # 生成订单号
    out_trade_no = f"ORD{int(time.time() * 1000)}"
    
    # 获取商品描述
    items = data.get('items', [])
    product_name = items[0]['title'] if items else "GoAbroady服务"
    desc = f"GoAbroady-{product_name}"
    if len(desc) > 100: desc = desc[:97] + "..."

    # 🔥 关键步骤：在数据库创建订单
    if user_id:
        try:
            # 确保用户存在
            if User.query.get(user_id):
                new_order = Order(
                    user_id=user_id,
                    out_trade_no=out_trade_no,
                    product_name=product_name,
                    amount=float(amount_yuan),
                    status='PENDING'
                )
                db.session.add(new_order)
                db.session.commit()
                logger.info(f"✅ 订单已入库: {out_trade_no}")
            else:
                logger.warning(f"用户ID {user_id} 不存在，跳过存库")
        except Exception as e:
            logger.error(f"订单入库失败 (不影响支付): {e}")
            db.session.rollback()

    # === 支付宝下单 ===
    if channel == 'alipay':
        client = get_alipay_client()
        if not client: return jsonify({'msg': '支付宝配置错误'}), 500
        
        try:
            model = AlipayTradePrecreateModel()
            model.out_trade_no = out_trade_no
            model.total_amount = str(amount_yuan)
            model.subject = desc
            
            request_obj = AlipayTradePrecreateRequest(biz_model=model)
            if os.getenv('ALIPAY_NOTIFY_URL'):
                request_obj.notify_url = os.getenv('ALIPAY_NOTIFY_URL')
            
            resp_str = client.execute(request_obj)
            resp = json.loads(resp_str)
            alipay_resp = resp.get('alipay_trade_precreate_response', {})
            
            if alipay_resp.get('code') == '10000':
                return jsonify({
                    'code_url': alipay_resp.get('qr_code'),
                    'order_no': out_trade_no,
                    'msg': '支付宝下单成功'
                })
            else:
                logger.error(f"支付宝下单失败: {alipay_resp.get('sub_msg')}")
                return jsonify({'msg': '支付宝下单失败', 'detail': alipay_resp}), 500
        except Exception as e:
            logger.error(f"支付宝异常: {e}")
            return jsonify({'msg': '系统支付异常'}), 500

    # === 微信下单 ===
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
            if isinstance(result, str): result = json.loads(result)
            
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

# ==================== 4. 查单接口 (修复 404 + 触发短信) ====================
@pay_bp.route('/query', methods=['GET'])
def query_order():
    """ 前端轮询查单，如果在本地开发收不到回调，这里也可以触发更新 """
    order_no = request.args.get('order_no')
    if not order_no:
        return jsonify({'paid': False})

    # 1. 查本地数据库 (如果回调先到了，这里直接返回成功)
    order = Order.query.filter_by(out_trade_no=order_no).first()
    if order and order.status == 'PAID':
        return jsonify({'paid': True, 'status': 'SUCCESS'})

    # 2. 如果本地未支付，去微信官方查 (作为兜底)
    is_paid = False
    wxpay = get_wxpay_client()
    if wxpay:
        try:
            code, result = wxpay.query(out_trade_no=order_no)
            if isinstance(result, str): result = json.loads(result)
            
            # 微信返回支付成功
            if code == 200 and result.get('trade_state') == 'SUCCESS':
                is_paid = True
        except: pass
    
    # 支付宝查单逻辑 (略)

    # 3. 如果查到已支付，更新数据库并补发短信
    if is_paid:
        if order and order.status != 'PAID':
            order.status = 'PAID'
            order.pay_time = datetime.now()
            db.session.commit()
            logger.info(f"✅ [查单] 订单 {order_no} 已支付，更新状态")
            
            # 🔥 触发短信 (国阳云)
            user = User.query.get(order.user_id)
            # 只有当用户绑定了手机号时才发送
            if user and user.phone:
                logger.info(f"🚀 准备发送短信给: {user.phone}")
                send_payment_success_sms(user.phone, order_no, order.product_name)
            else:
                logger.warning(f"用户 {user.id if user else 'Unknown'} 未绑定手机号，无法发送短信")
        
        return jsonify({'paid': True, 'status': 'SUCCESS'})

    return jsonify({'paid': False})

# ==================== 5. 回调通知 (支付宝) ====================
@pay_bp.route('/notify/alipay', methods=['POST'])
def notify_alipay():
    # ... (保持原样即可)
    return 'success'