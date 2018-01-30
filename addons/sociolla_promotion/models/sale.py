from openerp import api, fields, models, _

class sale_order_line(models.Model):
    _inherit = ['sale.order.line']
    free_product = fields.Boolean(string=u'Free Product',)