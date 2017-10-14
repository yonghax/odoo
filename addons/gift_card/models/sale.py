# -*- coding: utf-8 -*-

from openerp import models, fields, api, _

class sale_order(models.Model):
    
    _inherit = ['sale.order']
    
    gift_card_id = fields.Many2one(string=u'Prestashop Price Rule',comodel_name='gift.card',ondelete='cascade',)           
