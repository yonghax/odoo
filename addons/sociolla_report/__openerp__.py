# -*- coding: utf-8 -*-
{
    'name': "Sociolla Data Report",
    'summary': """
        List Data Report""",

    'description': """
        Data report PT. Social Bella Indonesia
    """,

    'author': "Yohanes Ho",
    'website': "http://www.sociolla.com",
    'category': 'Addon Sociolla',
    'version': '1',
    'installable': True,
    'sequence': 3,
    'depends': [
        'base', 
        'sociolla',
        'product', 
        'product_brand',
        'purchase',
        'stock',
        'sale_shop',
        'stock_account',
    ],

    'data': [
        'wizard/wizard_valuation_history.xml'
    ],  
}