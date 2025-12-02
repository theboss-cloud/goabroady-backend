# backend/get_wx_cert.py
import os
import logging
from dotenv import load_dotenv
from wechatpayv3 import WeChatPay, WeChatPayType

# 加载 .env
load_dotenv()

# 配置日志看详细报错
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wxpay_debug")

def test_init():
    print("\n🚀 开始微信支付配置自检...")
    
    # 1. 检查目录
    if not os.path.exists('./cert'):
        print("⚠️ ./cert 目录不存在，正在创建...")
        os.makedirs('./cert')
    
    # 2. 检查私钥文件
    key_path = os.getenv('WX_PRIVATE_KEY_PATH', './cert/apiclient_key.pem')
    if not os.path.exists(key_path):
        print(f"❌ 致命错误：找不到私钥文件：{key_path}")
        return

    with open(key_path, 'r') as f:
        private_key = f.read()
    
    mchid = os.getenv('WX_MCHID')
    serial_no = os.getenv('WX_CERT_SERIAL_NO')
    v3_key = os.getenv('WX_APIV3_KEY')

    print(f"👉 商户号: {mchid}")
    print(f"👉 证书序列号: {serial_no}")
    print(f"👉 APIv3密钥: {v3_key[:4]}******{v3_key[-4:]} (长度: {len(v3_key)})")

    try:
        # 初始化时，SDK 会自动尝试下载平台证书
        wxpay = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=mchid,
            private_key=private_key,
            cert_serial_no=serial_no,
            apiv3_key=v3_key,
            appid=os.getenv('WX_APPID'),
            notify_url='https://example.com', # 测试用，无所谓
            cert_dir='./cert', 
            logger=logger
        )
        print("\n✅ 恭喜！初始化成功！平台证书已下载到 ./cert 目录。")
        print("现在你可以重启 Flask 后端，支付功能应该能用了。")
        
    except Exception as e:
        err_msg = str(e)
        print("\n❌ 初始化失败！详细错误如下：")
        print(f"⚠️ {err_msg}")
        
        if "Decryption failed" in err_msg or "Tag mismatch" in err_msg:
            print("\n💡 诊断建议：【APIv3 密钥错误】")
            print("微信在下载证书时需要用你的 V3 密钥解密。解密失败说明密钥不对。")
            print("请去商户平台 -> API安全 -> 设置APIv3密钥，重新设置一个32位的，并更新到 .env。")
        
        elif "certificate" in err_msg.lower():
            print("\n💡 诊断建议：【证书序列号不匹配】")
            print("请检查 .env 里的 WX_CERT_SERIAL_NO 是否和 apiclient_key.pem 是一对的。")
            print("如果不确定，请去商户平台重新申请一套新的证书。")

if __name__ == '__main__':
    test_init()