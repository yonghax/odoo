from openerp import models, fields, api, _

class sale_order(models.Model):
    _inherit = 'sale.order'
    
    gift_card_id = fields.Many2one(
        string=u'Gift Card ID',
        comodel_name='gift.card',
        ondelete='cascade',
    )