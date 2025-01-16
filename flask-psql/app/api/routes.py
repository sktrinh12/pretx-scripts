from flask import request, jsonify
from app.api import bp
from app.functions import get_or_create_table
from sqlalchemy.exc import SQLAlchemyError
from app import db


@bp.route('/get-data', methods=['GET'])
def get_data():
    """Get rows from validity table"""
    user_name = request.args.get('user_name')
    if not user_name:
        return jsonify({'status': 'error', 'message': 'user_name parameter is required'}), 400
    try:
        table = get_or_create_table(user_name, create=False)
        stmt = table.select()
        result = db.session.execute(stmt).fetchall()
        rows = [{'exp_id': row.exp_id, 'valid': row.valid, 'invalid': row.invalid} for row in result]
        return jsonify({'data': rows}), 200

    except SQLAlchemyError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/update-data', methods=['POST'])
def update_data():
    """Update rows from the validity table."""
    user_name = request.args.get('user_name')
    if not user_name:
        return jsonify({'status': 'error', 'message': 'user_name parameter is required'}), 400
    
    table = get_or_create_table(user_name)
    data = request.json
    try:
        for exp_id, states in data.items():
            stmt = table.select().where(table.c.exp_id == exp_id)
            result = db.session.execute(stmt).fetchone()
            if result:
                stmt = (
                    table.update()
                    .where(table.c.exp_id == exp_id)
                    .values(valid=states['VALID'], invalid=states['INVALID'])
                )
            else:
                stmt = table.insert().values(
                    exp_id=exp_id, valid=states['VALID'], invalid=states['INVALID']
                )
            db.session.execute(stmt)
        db.session.commit()
        return jsonify({'status': 'success'}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
