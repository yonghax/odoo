# -*- coding: utf-8 -*-
from openerp import http

# class GiftCard(http.Controller):
#     @http.route('/gift_card/gift_card/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/gift_card/gift_card/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('gift_card.listing', {
#             'root': '/gift_card/gift_card',
#             'objects': http.request.env['gift_card.gift_card'].search([]),
#         })

#     @http.route('/gift_card/gift_card/objects/<model("gift_card.gift_card"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('gift_card.object', {
#             'object': obj
#         })