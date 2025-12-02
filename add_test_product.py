from app import create_app
from extensions import db
from models.product import Product

app = create_app()

with app.app_context():
    # 检查是否已存在
    existing = Product.query.filter_by(slug='test-1-cny').first()
    if existing:
        print("测试商品已存在，无需重复添加。")
    else:
        p = Product(
            slug='test-1-cny',
            title='微信支付测试商品 (1元)',
            summary='用于测试真实支付流程，支付后不可退款（或联系管理员退款）。',
            category='test',
            delivery='online',
            price=1.00,  # 1 元人民币
            duration_weeks=1,
            is_published=True,
            # 详情页字段
            service_promise='支付测试专用',
            detail_html='<p>这是一个测试商品，用于验证微信支付功能。</p>'
        )
        db.session.add(p)
        db.session.commit()
        print("✅ 成功添加 1 元测试商品！")
        print("商品 ID:", p.id)