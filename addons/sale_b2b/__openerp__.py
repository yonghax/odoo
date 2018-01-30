# -*- coding: utf-8 -*-
{
    'name': "Sales B2B Modular",
    'summary': """
        Sales B2B Modular""",

    'description': """
    """,

    'author': "Yohanes Ho",
    'website': "http://www.sociolla.com",
    'category': 'Sales B2B',
    'version': '0.1',
    'installable': True,
    'application': True,
    'sequence': 2,
    'depends': [
        'base', 
        'sale',
        'stock',
        'sale_shop',
        'sociolla', 
    ],

    'data': [
        'views/res_partner.xml',
        'reports/delivery_slip.xml',
    ],
}