# -*- coding: utf-8 -*-
from openerp import http

# class StockConsignment(http.Controller):
#     @http.route('/stock_consignment/stock_consignment/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_consignment/stock_consignment/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_consignment.listing', {
#             'root': '/stock_consignment/stock_consignment',
#             'objects': http.request.env['stock_consignment.stock_consignment'].search([]),
#         })

#     @http.route('/stock_consignment/stock_consignment/objects/<model("stock_consignment.stock_consignment"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_consignment.object', {
#             'object': obj
#         })