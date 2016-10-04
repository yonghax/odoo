from openerp.osv import fields, osv
from openerp import api, fields, models, _
from openerp.exceptions import UserError

class ProductBundle(models.Model):
    _name = 'product.bundle'

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade',
        help='Select product to add this bundle',
        index=True, 
        copy=False
    )