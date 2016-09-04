# -*- coding: utf-8 -*-
{
    'name': "Odoo - Prestashop Connector",
    'summary': """
        Synchronize data with Prestashop""",
        
    'description': """
        Version 0.1:
        
        - Import Shop Group
        
        - Import Shop
        
        - Import Customer

        Version 0.2
        
        - Import Product Attribute
        
        - Import Product Attribute Value
        
        - Import Product Attribute Line
        
        - Import Product Template
        
        - Import Product Variant
    """,
    'author': "Internal Development - PT. Social Bella Indonesia",
    'website': "http://www.sociolla.com",
    'category': 'Addon Sociolla',
    'version': '0.2',

    'depends': [
        'base',
        'connector',
        'sale_shop',
    ],

    'data': [
        'data/cron.xml',

        'views/prestashop_model_view.xml',
        'views/prestashoperpconnect_menu.xml',
        'views/partner_view.xml',
    ],
}