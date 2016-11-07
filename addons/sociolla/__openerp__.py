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
        'account', 
        'product', 
        'sale', 
        'product_brand',
        'purchase',
    ],

    'data': [
        'views/product_view.xml',
        'views/purchase_view.xml',
        'views/product_brand_view.xml',
        'views/res_users_view.xml',
        # 'reports/report_purchaseorder.xml',
        # 'reports/report_purchasequotation.xml',
    ],
}