# -*- coding: utf-8 -*-
{
    'name': "Sociolla Promotion",
    'summary': """
        Addon Promotion for Sociolla""",

    'description': """
        Module for maintain all promotion module for PT. Social Bella Indonesia
    """,

    'author': "Yohanes Ho",
    'website': "http://www.sociolla.com",
    'category': 'Addon Sociolla',
    'version': '0.1',
    'installable': True,
    'sequence': 3,
    'depends': [
        'base', 
        'sociolla',
        'product', 
        'prestashop_connector', 
        'product_brand',
        'purchase',
        'stock',
        'sale_shop'
    ],

    'data': [
        'views/product_view.xml',
    ],  
}