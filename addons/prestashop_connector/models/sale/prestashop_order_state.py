from openerp import models, fields, api, _
from ...unit.backend_adapter import GenericAdapter


class prestashop_order_state(models.Model):
    _name = 'prestashop.order.state'
    _inherit = 'prestashop.binding'
   
    name = fields.Char(string = 'Name', size=64)