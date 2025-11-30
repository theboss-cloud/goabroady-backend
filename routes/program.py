from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from models.program import Program
from extensions import db

program_bp = Blueprint('program', __name__)

# 获取所有项目列表
@program_bp.route('/api/programs', methods=['GET'])
@jwt_required()
def get_programs():
    programs = Program.query.all()
    return jsonify([p.to_dict() for p in programs])

# 获取单个项目详情
@program_bp.route('/api/programs/<int:program_id>', methods=['GET'])
@jwt_required()
def get_program(program_id):
    program = Program.query.get_or_404(program_id)
    return jsonify(program.to_dict())

# 新增项目
@program_bp.route('/api/programs', methods=['POST'])
@jwt_required()
def add_program():
    data = request.get_json()
    program = Program(**data)
    db.session.add(program)
    db.session.commit()
    return jsonify({"msg": "创建成功", "id": program.id})

# 更新项目
@program_bp.route('/api/programs/<int:program_id>', methods=['PUT'])
@jwt_required()
def update_program(program_id):
    program = Program.query.get_or_404(program_id)
    data = request.get_json()
    for key, value in data.items():
        setattr(program, key, value)
    db.session.commit()
    return jsonify({"msg": "更新成功"})

# 删除项目
@program_bp.route('/api/programs/<int:program_id>', methods=['DELETE'])
@jwt_required()
def delete_program(program_id):
    program = Program.query.get_or_404(program_id)
    db.session.delete(program)
    db.session.commit()
    return jsonify({"msg": "删除成功"})
