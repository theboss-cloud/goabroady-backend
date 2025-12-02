# routes/pay.py
import os
import time
import json
import logging
import traceback
from flask import Blueprint, request, jsonify
from wechatpayv3 import WeChatPay, WeChatPayType

pay_bp = Blueprint('pay', __name__, url_prefix='/api/pay')

# 初始化日志
logger = logging.getLogger(__name__)

def get_wxpay_client():
    """懒加载获取微信支付客户端实例"""
    try:
        # 从环境变量或 Config 读取配置
        private_key_path = os.getenv('WX_PRIVATE_KEY_PATH', './cert/apiclient_key.pem')
        
        # 确保私钥文件存在
        if not os.path.exists(private_key_path):
            logger.error(f"找不到私钥文件: {private_key_path}")
            return None

        with open(private_key_path, 'r') as f:
            private_key = f.read()

        return WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=os.getenv('WX_MCHID'),
            private_key=private_key,
            cert_serial_no=os.getenv('WX_CERT_SERIAL_NO'),
            apiv3_key=os.getenv('WX_APIV3_KEY'),
            appid=os.getenv('WX_APPID'),
            notify_url=os.getenv('WX_NOTIFY_URL'),
            cert_dir='./cert',  # 平台证书缓存目录
            logger=logger
        )
    except Exception as e:
        logger.error(f"微信支付初始化失败: {e}")
        return None

@pay_bp.route('/prepare', methods=['POST'])
def prepare_pay():
    """
    统一下单接口
    前端调用此接口获取 code_url (二维码链接)
    """
    data = request.get_json() or {}
    amount_yuan = data.get('amount', 0)
    items = data.get('items', [])
    
    # 1. 基础校验
    if amount_yuan <= 0:
        return jsonify({'msg': '金额必须大于0'}), 400

    # 2. 生成本地订单号
    out_trade_no = f"ORD{int(time.time() * 1000)}"
    
    # 3. 构造商品描述
    description = f"GoAbroady服务-{items[0]['title']}" if items else "GoAbroady留学服务"
    if len(description) > 127: description = description[:124] + "..."

    # 4. 调用微信下单
    wxpay = get_wxpay_client()
    if not wxpay:
        return jsonify({'msg': '支付配置错误'}), 500

    # 金额转为分
    amount_fen = int(amount_yuan * 100)
    
    try:
        code, result = wxpay.pay(
            description=description,
            out_trade_no=out_trade_no,
            amount={'total': amount_fen},
            pay_type=WeChatPayType.NATIVE
        )
        
        # 🔥 兼容处理：result 可能是 JSON 字符串
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                pass

        # 检查结果
        if code in [200, 201, 202] and isinstance(result, dict) and result.get('code_url'):
            
            # TODO: 建议在这里把订单存入数据库 (状态: PENDING)
            # Order.create(...)
            
            return jsonify({
                'code_url': result['code_url'],
                'order_no': out_trade_no,
                'msg': '下单成功'
            })
        else:
            logger.error(f"微信下单失败: code={code}, result={result}")
            return jsonify({'msg': '微信下单失败', 'detail': result}), 500

    except Exception as e:
        logger.error(f"支付异常: {e}")
        traceback.print_exc()
        return jsonify({'msg': '系统支付异常'}), 500


@pay_bp.route('/query', methods=['GET'])
def query_order():
    """
    前端轮询查单接口
    """
    order_no = request.args.get('order_no')
    if not order_no:
        return jsonify({'paid': False})

    wxpay = get_wxpay_client()
    if not wxpay:
        return jsonify({'paid': False})

    try:
        # 调用微信查单
        code, result = wxpay.query(out_trade_no=order_no)
        
        # 🔥🔥🔥【关键修复】：这里也必须加 JSON 解析，否则查单会报 500 错误
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                pass
        
        # 确保 result 是字典后再操作
        if not isinstance(result, dict):
            logger.error(f"查单返回非字典格式: {result}")
            return jsonify({'paid': False, 'msg': '查单响应格式错误'})

        trade_state = result.get('trade_state')

        # trade_state: SUCCESS, REFUND, NOTPAY, CLOSED...
        if code == 200 and trade_state == 'SUCCESS':
            # TODO: 更新数据库订单状态为 'PAID'
            return jsonify({'paid': True, 'status': 'SUCCESS'})
        
        return jsonify({'paid': False, 'status': trade_state})

    except Exception as e:
        logger.error(f"查单接口异常: {e}")
        traceback.print_exc()
        return jsonify({'paid': False, 'msg': str(e)})


@pay_bp.route('/notify', methods=['POST'])
def notify():
    """
    微信支付回调通知 (Webhook)
    """
    wxpay = get_wxpay_client()
    if not wxpay:
        return jsonify({'code': 'FAIL', 'message': 'INIT_ERROR'}), 500

    try:
        # 验签并解密
        # 注意：wxpay.callback 内部已经处理了 json.loads，通常返回的是字典
        result = wxpay.callback(request.headers, request.data)
        
        if result and isinstance(result, dict) and result.get('event_type') == 'TRANSACTION.SUCCESS':
            resource = result.get('resource', {})
            # 解密后的数据在 resource 字典里（如果 SDK 解密成功的话）
            # 或者 SDK 直接返回解密后的明文内容
            
            # 打印日志方便调试
            logger.info(f"收到支付成功回调: {result}")
            
            # 根据实际解密内容获取订单号
            # out_trade_no = result.get('out_trade_no') 
            
            # TODO: 务必在这里做幂等处理，更新数据库状态，发放权益
            
            return jsonify({'code': 'SUCCESS', 'message': 'OK'})
            
    except Exception as e:
        logger.error(f"回调处理异常: {e}")
        traceback.print_exc()
        
    return jsonify({'code': 'FAIL', 'message': 'ERROR'}), 400