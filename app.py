# app.py
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, jwt_required, get_jwt
from flask_cors import CORS
from dotenv import load_dotenv
from flask_migrate import Migrate

from config import Config
from extensions import db

# ---- 导入各个蓝图 ----
from routes.auth import auth_bp
from routes.program_admin import admin_program_bp
from routes.program_public import public_program_bp
from routes.upload import upload_bp
from routes.profile import profile_bp
from routes.predict import predict_bp
from routes.dashboard import dashboard_bp
from routes.application import application_bp
from routes.admin_manage import admin_manage_bp
from routes.program_stats import program_stats_bp
from routes.cases_public import cases_public_bp
from routes.cases_admin import cases_admin_bp
from routes.program_export import program_export_bp
from routes.image_cache import image_cache_bp
from routes.media_public import media_public_bp
from routes.assessment import assessment_bp
from routes.meta import meta_bp
from routes.me import bp_me
from routes.messages import messages_bp
from routes.tasks import tasks_bp
from routes.scholarship_match import scholar_bp
from routes.order import orders_bp
from routes.billing import billing_bp
from routes.pay import pay_bp
from routes.product_public import public_product_bp
from routes.product_admin import admin_product_bp
from routes.me_services import me_services_bp  # ✅ 新增：我的服务/权益

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---- 初始化扩展 ----
    db.init_app(app)
    from models.assessment_result import AssessmentResult  # noqa: F401
    from models.product import Product  # noqa: F401
    from models.order import Order, OrderItem, ServiceEntitlement  # noqa: F401

    JWTManager(app)
    Migrate(app, db)

    # ---- CORS ----
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:8848",
                    "http://127.0.0.1:8848",
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    # 这里可以按需加你的 admin 域名
                ],
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "Authorization"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            }
        },
    )

    # ---- 注册蓝图 ----
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_program_bp)
    app.register_blueprint(public_program_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(application_bp)
    app.register_blueprint(admin_manage_bp)
    app.register_blueprint(program_stats_bp)
    app.register_blueprint(cases_public_bp)
    app.register_blueprint(cases_admin_bp)
    app.register_blueprint(program_export_bp)
    app.register_blueprint(image_cache_bp)
    app.register_blueprint(media_public_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(meta_bp)
    app.register_blueprint(bp_me)
    app.register_blueprint(messages_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(scholar_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(public_product_bp)
    app.register_blueprint(admin_product_bp)
    app.register_blueprint(pay_bp)
    app.register_blueprint(me_services_bp)  # ✅ 注册新的 /api/me/services

    # ---- 健康检查 ----
    @app.get("/")
    def health():
        return jsonify({"status": "ok"})

    # ---- 后台动态路由（保持简单版本，你可以按需扩展）----
    @app.get("/api/get-async-routes")
    @jwt_required()
    def get_async_routes():
        claims = get_jwt() or {}
        roles = claims.get("roles") or claims.get("role") or []
        if isinstance(roles, str):
            roles = [roles]

        # 这里给一个精简示例，真实项目中你可以根据 roles 动态调整
        routes = [
            {
                "path": "/dashboard",
                "name": "Dashboard",
                "component": "dashboard/overview",
                "meta": {"title": "首页", "icon": "ep:home-filled", "roles": ["admin", "staff"]},
            },
            {
                "path": "/programs",
                "name": "ProgramManage",
                "component": "layout",
                "redirect": "/programs/list",
                "meta": {"title": "留学项目", "icon": "icon-park-outline:ad-product", "roles": ["admin", "staff"]},
            },
        ]
        return jsonify({"routes": routes})

    return app
