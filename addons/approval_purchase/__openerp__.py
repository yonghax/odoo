# -*- coding: utf-8 -*-
{
    'name': "Purchasing Approval",
    'summary': """
        Extra application to approve application""",

    'description': """
    """,

    'author': "Yohanes Ho",
    'website': "https://www.sociolla.com",
    'category': 'Addon Sociolla',
    'version': '1.0',
    'installable': True,
    'sequence': 3,
    'depends': [
        'base', 
        'sociolla',
        'purchase', 
        'stock',
        'sale_shop'
    ],

    'data': [
        'views/approval_purchase.xml',
        'views/company_view.xml',
    ],  
}