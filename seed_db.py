"""
seed_db.py — Import Sample_Data.xlsx into the PartnerTrack database.
Run AFTER `flask db create_all` or just `python app.py` once.
Usage:
    python seed_db.py --file Sample_Data.xlsx
"""
import argparse
import sys
import pandas as pd
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('--file', default='Sample_Data.xlsx', help='Path to the Excel file')
parser.add_argument('--db', required=True, help='Database URL (required)')
args = parser.parse_args()

# Bootstrap app context
import os
os.environ.setdefault('DATABASE_URL', args.db)
from app import app, db, StockItem, PartnerRule, SalesLog

def safe_float(v, default=0.0):
    try:
        return float(v) if pd.notna(v) else default
    except:
        return default

def safe_date(v):
    if pd.isna(v):
        return None
    try:
        return pd.to_datetime(v).date()
    except:
        return None

with app.app_context():
    db.create_all()

    xl = pd.ExcelFile(args.file)

    # ── Partner Rules ───────────────────────────────────────────────────────
    print('Seeding partner rules…')
    rules_df = pd.read_excel(xl, sheet_name='Partner_Rule_Table', header=0)
    rules_df.columns = ['category', 'rule_type', 'kali_rate', 'al_rate', 'notes']
    for _, row in rules_df.iterrows():
        if pd.isna(row['category']):
            continue
        cat = str(row['category']).strip()
        if not PartnerRule.query.filter_by(category=cat).first():
            db.session.add(PartnerRule(
                category=cat,
                rule_type=str(row['rule_type']).strip(),
                kali_rate=safe_float(row['kali_rate']),
                al_rate=str(row['al_rate']).strip() if pd.notna(row['al_rate']) else 'LEFTOVER',
                notes=str(row['notes']).strip() if pd.notna(row['notes']) else None
            ))
    db.session.commit()
    print(f'  → {PartnerRule.query.count()} rules loaded.')

    # ── Stock Master ────────────────────────────────────────────────────────
    print('Seeding stock master…')
    stock_df = pd.read_excel(xl, sheet_name='Stock_Master')
    print(stock_df)
    for _, row in stock_df.iterrows():
        if pd.isna(row.get('Item_Code')):
            continue
        db.session.add(StockItem(
            item_code=str(row['Item_Code']).strip(),
            description=str(row.get('Description', '')).strip(),
            brand=str(row.get('Brand', '')).strip(),
            category=str(row.get('Category', '')).strip(),
            current_qty=safe_float(row.get('Current_Quantity')),
            sales_qty=safe_float(row.get('Sales_Quantity')),
            unit=str(row.get('Unit', '')).strip() if pd.notna(row.get('Unit')) else '',
            cost_rm=safe_float(row.get('Cost (RM)')),
            selling_price=safe_float(row.get('Selling_Price (RM)')),
            purchased_date=safe_date(row.get('Purchased_Date'))
        ))
    db.session.commit()
    print(f'  → {StockItem.query.count()} stock items loaded.')

    # ── Sales Log (current month sheet) ────────────────────────────────────
    sales_sheets = [s for s in xl.sheet_names if s.startswith('Sales_Log_')]
    for sheet_name in sales_sheets:
        month_year = sheet_name.replace('Sales_Log_', '')
        print(f'Seeding sales log for {month_year}…')
        sales_df = pd.read_excel(xl, sheet_name=sheet_name, header=0)

        # Only process rows where Quantity_Sold is present
        if 'Quantity_Sold' not in sales_df.columns:
            print(f'  → Skipped (no Quantity_Sold column)')
            continue
        sales_df = sales_df[pd.notna(sales_df['Quantity_Sold'])]

        for _, row in sales_df.iterrows():
            if pd.isna(row.get('Item_Code')):
                continue
            qty   = safe_float(row.get('Quantity_Sold'))
            price = safe_float(row.get('Actual_Selling_Price'))
            cost  = safe_float(row.get('Cost (RM)'))
            revenue    = safe_float(row.get('Revenue_Per_Sales'))
            al_share   = safe_float(row.get('A.L_Share'))
            kali_share = safe_float(row.get('KALI_Share'))
            gross      = safe_float(row.get('Gross_Profit'))
            db.session.add(SalesLog(
                item_code=str(row['Item_Code']).strip(),
                description=str(row.get('Description', '')).strip(),
                brand=str(row.get('Brand', '')).strip() if pd.notna(row.get('Brand')) else '',
                category=str(row.get('Category', '')).strip(),
                month_year=month_year,
                quantity_sold=qty,
                actual_selling_price=price,
                checked_date=safe_date(row.get('Checked_Date')),
                cost_rm=cost,
                rule_type=str(row.get('RuleType', '')).strip() if pd.notna(row.get('RuleType')) else None,
                al_rate=str(row.get('A.L_Rate', 'LEFTOVER')).strip() if pd.notna(row.get('A.L_Rate')) else 'LEFTOVER',
                kali_rate=safe_float(row.get('KALI_Rate')),
                revenue_per_sales=revenue,
                cost_per_sale=safe_float(row.get('Cost_Per_Sale')),
                gross_profit=gross,
                al_share=al_share,
                kali_share=kali_share
            ))
        db.session.commit()
        print(f'  → Sales log for {month_year} loaded.')

    print('\n✅ Seed complete!')
