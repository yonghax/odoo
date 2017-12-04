from openerp import api, fields, models, _

class stock_move(models.Model):
    _inherit = 'stock.move'
    
    is_switchover_stock = fields.Boolean(string='Switchover stock')
    is_gwp_free = fields.Boolean(string=u'Free Product',default=False,)
    source_date = fields.Datetime(string=u'Source Date',)
    inventory_line_id = fields.Many2one(string=u'Inventory Line ID',comodel_name='stock.inventory.line',)
    