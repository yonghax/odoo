# -*- coding: utf-8 -*-
{
    'name': "Sale Consignment",

    'summary': """
        Custom addon to maintain consignment sale""",

    'description': """
        * Generate sale consignment report
        * Reconcilation Sales Consignment
    """,

    'author': "Yohanes Ho",
    'website': "",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Sale Consignment',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock', 'account', 'product', 'product_brand', 'purchase', 'sale'],

    # always loaded
    'data': [
        'views/views.xml',
        'report/reports.xml',
        'views/menuitems.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}