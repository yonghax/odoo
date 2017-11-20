from openerp import api, fields, models, _

class stock_move(models.Model):
    _inherit = 'stock.move'
    
    is_switchover_stock = fields.Boolean(string='Switchover stock')
