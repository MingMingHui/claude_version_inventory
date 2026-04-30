from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
from flask import render_template
from sqlalchemy import func, case
from dotenv import load_dotenv

app = Flask(__name__, template_folder='backend/templates')
CORS(app)
load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
if not app.config['SQLALCHEMY_DATABASE_URI']:
    raise ValueError("ERROR: SQLALCHEMY_DATABASE_URI environment variable not set")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── Models ────────────────────────────────────────────────────────────────────

class StockItem(db.Model):
    __tablename__ = 'stock_master'
    id            = db.Column(db.Integer, primary_key=True)
    item_code     = db.Column(db.String(50), nullable=False)
    description   = db.Column(db.String(200))
    brand         = db.Column(db.String(100))
    category      = db.Column(db.String(100))
    current_qty   = db.Column(db.Float, default=0)
    sales_qty     = db.Column(db.Float, default=0)
    unit          = db.Column(db.String(20))
    cost_rm       = db.Column(db.Float, default=0)
    selling_price = db.Column(db.Float, default=0)
    purchased_date= db.Column(db.Date)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PartnerRule(db.Model):
    __tablename__ = 'partner_rules'
    id            = db.Column(db.Integer, primary_key=True)
    category      = db.Column(db.String(100), nullable=False, unique=True)
    rule_type     = db.Column(db.String(50))   # Fixed_Per_Unit | Shared_50 | Fixed_Per_Job | Fixed_Per_Service
    kali_rate     = db.Column(db.Float, default=0)   # KALI (Pihak B)
    al_rate       = db.Column(db.String(50))          # AL   (Pihak A) – may be LEFTOVER
    notes         = db.Column(db.String(200))


class SalesLog(db.Model):
    __tablename__ = 'sales_log'
    __table_args__ = (
        db.Index('idx_sales_month_year', 'month_year'),
        db.Index('idx_sales_category', 'category'),
        db.Index('idx_sales_stock_item', 'stock_item_id'),
    )    
    id                   = db.Column(db.Integer, primary_key=True)
    stock_item_id        = db.Column(db.Integer, db.ForeignKey('stock_master.id'), index=True)
    item_code            = db.Column(db.String(50))
    description          = db.Column(db.String(200))
    brand                = db.Column(db.String(100))
    category             = db.Column(db.String(100))
    month_year           = db.Column(db.String(6))    # YYYYMM
    quantity_sold        = db.Column(db.Float, default=0)
    actual_selling_price = db.Column(db.Float, default=0)
    checked_date         = db.Column(db.Date)
    cost_rm              = db.Column(db.Float, default=0)
    rule_type            = db.Column(db.String(50))
    al_rate              = db.Column(db.String(50))
    kali_rate            = db.Column(db.Float, default=0)
    revenue_per_sales    = db.Column(db.Float, default=0)
    cost_per_sale        = db.Column(db.Float, default=0)
    gross_profit         = db.Column(db.Float, default=0)
    al_share             = db.Column(db.Float, default=0)
    kali_share           = db.Column(db.Float, default=0)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)


class MonthlySummary(db.Model):
    __tablename__ = 'monthly_summary'
    id         = db.Column(db.Integer, primary_key=True)
    month_year = db.Column(db.String(6))
    category   = db.Column(db.String(100))
    al_share   = db.Column(db.Float, default=0)
    kali_share = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Helpers ───────────────────────────────────────────────────────────────────

def calculate_shares(category, rule_type, kali_rate, al_rate_str, revenue, cost):
    gross = revenue - cost
    if rule_type == 'Fixed_Per_Unit':
        kali_share = kali_rate
        al_share   = revenue - kali_rate if al_rate_str == 'LEFTOVER' else float(al_rate_str)
    elif rule_type == 'Shared_50':
        kali_share = revenue * kali_rate
        al_share   = revenue * float(al_rate_str) if al_rate_str != 'LEFTOVER' else revenue * 0.5
    elif rule_type in ('Fixed_Per_Job', 'Fixed_Per_Service'):
        kali_share = revenue * kali_rate if kali_rate < 1 else kali_rate
        al_share   = revenue - kali_share
    else:
        kali_share = 0
        al_share   = 0
    return round(al_share, 2), round(kali_share, 2)
# ── Stock Master CRUD ─────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stock', methods=['GET'])
def get_stock():
    items = StockItem.query.all()
    return jsonify([{
        'id': i.id, 'item_code': i.item_code, 'description': i.description,
        'brand': i.brand, 'category': i.category, 'current_qty': i.current_qty,
        'sales_qty': i.sales_qty, 'unit': i.unit, 'cost_rm': i.cost_rm,
        'selling_price': i.selling_price,
        'purchased_date': i.purchased_date.isoformat() if i.purchased_date else None
    } for i in items])


@app.route('/api/stock', methods=['POST'])
def add_stock():
    d = request.json
    item = StockItem(
        item_code=d['item_code'], description=d.get('description'),
        brand=d.get('brand'), category=d.get('category'),
        current_qty=d.get('current_qty', 0), sales_qty=d.get('sales_qty', 0),
        unit=d.get('unit'), cost_rm=d.get('cost_rm', 0),
        selling_price=d.get('selling_price', 0),
        purchased_date=datetime.strptime(d['purchased_date'], '%Y-%m-%d').date() if d.get('purchased_date') else None
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'id': item.id}), 201


@app.route('/api/stock/<int:item_id>', methods=['PUT'])
def update_stock(item_id):
    item = StockItem.query.get_or_404(item_id)
    d = request.json
    for field in ['item_code','description','brand','category','current_qty','sales_qty','unit','cost_rm','selling_price']:
        if field in d:
            setattr(item, field, d[field])
    if d.get('purchased_date'):
        item.purchased_date = datetime.strptime(d['purchased_date'], '%Y-%m-%d').date()
    db.session.commit()
    return jsonify({'status': 'updated'})


@app.route('/api/stock/<int:item_id>', methods=['DELETE'])
def delete_stock(item_id):
    item = StockItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'status': 'deleted'})


# ── Partner Rules ─────────────────────────────────────────────────────────────

@app.route('/api/rules', methods=['GET'])
def get_rules():
    rules = PartnerRule.query.all()
    return jsonify([{
        'id': r.id, 'category': r.category, 'rule_type': r.rule_type,
        'kali_rate': r.kali_rate, 'al_rate': r.al_rate, 'notes': r.notes
    } for r in rules])


@app.route('/api/rules', methods=['POST'])
def add_rule():
    d = request.json
    rule = PartnerRule(
        category=d['category'], rule_type=d['rule_type'],
        kali_rate=d.get('kali_rate', 0), al_rate=d.get('al_rate', 'LEFTOVER'),
        notes=d.get('notes')
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify({'id': rule.id}), 201


@app.route('/api/rules/<int:rule_id>', methods=['PUT'])
def update_rule(rule_id):
    rule = PartnerRule.query.get_or_404(rule_id)
    d = request.json
    for field in ['category','rule_type','kali_rate','al_rate','notes']:
        if field in d:
            setattr(rule, field, d[field])
    db.session.commit()
    return jsonify({'status': 'updated'})


# ── Sales Log ─────────────────────────────────────────────────────────────────

@app.route('/api/sales', methods=['GET'])
def get_sales():
    month_year = request.args.get('month_year')
    q = SalesLog.query
    if month_year:
        q = q.filter_by(month_year=month_year)
    logs = q.all()
    return jsonify([{
        'id': l.id, 'item_code': l.item_code, 'description': l.description,
        'category': l.category, 'month_year': l.month_year,
        'quantity_sold': l.quantity_sold, 'actual_selling_price': l.actual_selling_price,
        'checked_date': l.checked_date.isoformat() if l.checked_date else None,
        'rule_type': l.rule_type, 'al_rate': l.al_rate, 'kali_rate': l.kali_rate,
        'revenue_per_sales': l.revenue_per_sales, 'cost_per_sale': l.cost_per_sale,
        'gross_profit': l.gross_profit, 'al_share': l.al_share, 'kali_share': l.kali_share
    } for l in logs])


@app.route('/api/sales', methods=['POST'])
def add_sale():
    d = request.json
    rule = PartnerRule.query.filter_by(category=d.get('category')).first()
    qty   = float(d.get('quantity_sold', 0))
    price = float(d.get('actual_selling_price', 0))
    cost  = float(d.get('cost_rm', 0))
    revenue  = qty * price
    total_cost = qty * cost
    gross    = revenue - total_cost

    al_share, kali_share = 0, 0
    if rule:
        al_share, kali_share = calculate_shares(
            rule.category, rule.rule_type, rule.kali_rate * qty,
            rule.al_rate, revenue, total_cost
        )

    log = SalesLog(
        stock_item_id=d.get('stock_item_id'),
        item_code=d['item_code'], description=d.get('description'),
        brand=d.get('brand'), category=d.get('category'),
        month_year=d['month_year'], quantity_sold=qty,
        actual_selling_price=price,
        checked_date=datetime.strptime(d['checked_date'], '%Y-%m-%d').date() if d.get('checked_date') else date.today(),
        cost_rm=cost, rule_type=rule.rule_type if rule else None,
        al_rate=rule.al_rate if rule else None,
        kali_rate=rule.kali_rate if rule else 0,
        revenue_per_sales=revenue, cost_per_sale=total_cost,
        gross_profit=gross, al_share=al_share, kali_share=kali_share
    )
    db.session.add(log)

    # update stock qty
    stock = StockItem.query.get(d.get('stock_item_id'))
    if stock:
        stock.current_qty = max(0, stock.current_qty - qty)
        stock.sales_qty   = (stock.sales_qty or 0) + qty

    db.session.commit()
    return jsonify({'id': log.id}), 201


# ── Monthly Summary ───────────────────────────────────────────────────────────

@app.route('/api/summary/<month_year>', methods=['GET'])
def get_summary(month_year):
    # Aggregate at database level
    summary_rows = db.session.query(
        func.coalesce(SalesLog.category, 'Unknown').label('category'),
        func.sum(SalesLog.al_share).label('al_share'),
        func.sum(SalesLog.kali_share).label('kali_share')
    ).filter(
        SalesLog.month_year == month_year
    ).group_by(SalesLog.category).all()
    
    rows = [
        {
            'category': r.category,
            'al_share': round(float(r.al_share or 0), 2),
            'kali_share': round(float(r.kali_share or 0), 2)
        }
        for r in summary_rows
    ]
    
    total_al = sum(r['al_share'] for r in rows)
    total_kali = sum(r['kali_share'] for r in rows)
    
    return jsonify({
        'month_year': month_year,
        'rows': rows,
        'total_al': round(total_al, 2),
        'total_kali': round(total_kali, 2)
    })

@app.route('/api/summary/months', methods=['GET'])
def available_months():
    months = db.session.query(SalesLog.month_year).distinct().all()
    return jsonify([m[0] for m in months if m[0]])


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    # Query 1: Stock stats (one query)
    stock_stats = db.session.query(
        func.count(StockItem.id).label('total'),
        func.count(
            case((StockItem.current_qty <= 2, 1))
        ).label('low_stock')
    ).first()
    
    # Query 2: Recent month summary
    recent_month_result = db.session.query(
        SalesLog.month_year
    ).order_by(SalesLog.month_year.desc()).limit(1).first()
    
    recent_month = recent_month_result[0] if recent_month_result else None
    
    # Query 3: Aggregate for that month (in database)
    al_total, kali_total = 0, 0
    if recent_month:
        result = db.session.query(
            func.sum(SalesLog.al_share).label('al_sum'),
            func.sum(SalesLog.kali_share).label('kali_sum')
        ).filter(SalesLog.month_year == recent_month).first()
        
        al_total = round(float(result.al_sum or 0), 2)
        kali_total = round(float(result.kali_sum or 0), 2)
    
    return jsonify({
        'total_stock_items': stock_stats.total or 0,
        'low_stock_count': stock_stats.low_stock or 0,
        'recent_month': recent_month,
        'al_earnings': al_total,
        'kali_earnings': kali_total
    })

# ── Health Check ─────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():  # NO     
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow()}), 200
# ── Seed data from Excel ──────────────────────────────────────────────────────

@app.route('/api/seed', methods=['POST'])
def seed_from_excel():
    import pandas as pd
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file'}), 400

    xl = pd.ExcelFile(f)

    # Partner rules
    rules_df = pd.read_excel(xl, sheet_name='Partner_Rule_Table', header=0)
    rules_df.columns = ['category','rule_type','kali_rate','al_rate','notes']
    for _, row in rules_df.iterrows():
        if pd.isna(row['category']):
            continue
        existing = PartnerRule.query.filter_by(category=str(row['category'])).first()
        if not existing:
            db.session.add(PartnerRule(
                category=str(row['category']), rule_type=str(row['rule_type']),
                kali_rate=float(row['kali_rate']) if pd.notna(row['kali_rate']) else 0,
                al_rate=str(row['al_rate']), notes=str(row['notes']) if pd.notna(row['notes']) else None
            ))

    # Stock master
    stock_df = pd.read_excel(xl, sheet_name='Stock_Master', header=1)
    for _, row in stock_df.iterrows():
        if pd.isna(row.get('Item_Code')):
            continue
        pd_date = None
        if pd.notna(row.get('Purchased_Date')):
            try:
                pd_date = pd.to_datetime(row['Purchased_Date']).date()
            except:
                pass
        db.session.add(StockItem(
            item_code=str(row['Item_Code']), description=str(row.get('Description','')),
            brand=str(row.get('Brand','')), category=str(row.get('Category','')),
            current_qty=float(row.get('Current_Quantity', 0)) if pd.notna(row.get('Current_Quantity')) else 0,
            sales_qty=float(row.get('Sales_Quantity', 0)) if pd.notna(row.get('Sales_Quantity')) else 0,
            unit=str(row.get('Unit','')),
            cost_rm=float(row.get('Cost (RM)', 0)) if pd.notna(row.get('Cost (RM)')) else 0,
            selling_price=float(row.get('Selling_Price (RM)', 0)) if pd.notna(row.get('Selling_Price (RM)')) else 0,
            purchased_date=pd_date
        ))

    db.session.commit()
    return jsonify({'status': 'seeded'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
