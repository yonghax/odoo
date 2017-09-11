# -*- coding: utf-8 -*-
{
    'name': "Stock Consignment",

    'summary': """
        Custom addon to maintain consignment stock""",

    'description': """
        * Maintain consignment stock and combine partial stock is yours.

        * Update journal structure from consignee stock.
    """,

    'author': "Yohanes Ho",
    'website': "",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Stock Consignment',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock', 'account', 'product', 'product_brand', 'purchase'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/purchase_view.xml',
        'views/stock_view.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}