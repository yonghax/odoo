from openerp import models, fields, api

class res_partner(models.Model):
    _inherit = 'res.partner'
    
    consignment = fields.Boolean(
        string='Consignment',
        default = False
    )
    outlet_type = fields.Selection(
        string=u'Customer Type',
        default='direct',
        selection=[('mt', 'Modern Trade'), ('gt', 'General Trade'), ('direct', 'Direct')]
    )
    warehouse_ids = fields.One2many(
        'stock.warehouse',
        'partner_id',
        string='Warehouse', 
        readonly=True,
    )