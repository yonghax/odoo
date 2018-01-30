from datetime import datetime
from openerp import api, fields, models, SUPERUSER_ID, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

import openerp.addons.decimal_precision as dp

class res_company(models.Model):
    _inherit = ['res.company']
    
    po_double_validation = fields.Selection(
        selection=[
            ('one_step', 'Confirm purchase orders in one step'), 
            ('two_step', 'Required purchase manager to approve purchase order.'),
            ('three_step', 'Required director level to approve purchase order within range amount.'),
        ], default='one_step',\
        help="Provide a double validation mechanism for purchases")
    
    po_third_validation_amount = fields.Monetary(string=u'Request third validation amount',)