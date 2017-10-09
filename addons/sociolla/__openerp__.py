# -*- coding: utf-8 -*-
{
    'name': "Sociolla Addons",
    'summary': """
        Addon feature for PT. Social Bella Indonesia""",

    'description': """
        Version 0.1:
            - Add posting journal Sales Discount
            - Add posting journal Sales Return
            - Add grouping brand on report sales analytic
        
        Version 0.2:
            - Add Connector Odoo - Prestashop 
        
        Version 0.3:
            - Add Discount Purchase Order
            
        Version 0.4:
            - Add Product Bundle

        Version 0.5:
            - Add e-signature users
        
        Version 0.6:
            - AR base from payment method

        Version 0.7:
            - Switch-Over Product Feature
    """,

    'author': "Internal Development - PT. Social Bella Indonesia",
    'website': "http://www.sociolla.com",
    'category': 'Addon Sociolla',
    'version': '0.5',
    'installable': True,
    'application': True,
    'sequence': 1,
    
    'depends': [
        'base', 
        'mail',
        'account', 
        'product', 
        'sale', 
        'product_brand',
        'purchase',
        'stock',
        'sale_shop'
    ],

    'data': [
        'security/custom_sociolla_security.xml',
        # 'security/ir.model.access.csv',
        'views/product_view.xml',
        'views/purchase_view.xml',
        # 'views/product_brand_view.xml',
        'views/res_users_view.xml',
        'views/stock_view.xml',
        'views/shop_view.xml',
        'views/payment_method_view.xml',
        'views/switchover_product_view.xml',
        'views/account_view.xml',
        'views/partner.xml',
        'views/currency_view.xml',
        # 'reports/report_stock_picking_slip.xml',
        'reports/account_invoice_report_view.xml',
        # 'security/ir.model.access.csv',
        # 'reports/report_purchaseorder.xml',
        # 'reports/report_purchasequotation.xml',
    ],
}