from openerp.osv import fields, osv
from openerp import api, fields, models, _
from openerp.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    is_product_bundle = fields.Boolean(
        string='Product Bundle',
        required=False,
        default=False,
        help="Specify if the product is pack bundle"
    )

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    product_bundle = fields.One2many(
        'product.bundle', 
        'parent_product_id', 
        string='Parent Product', 
        copy=True
    )

class ProductBundle(models.Model):
    _name = 'product.bundle'

    parent_product_id = fields.Many2one(
        'product.product', 
        string='Parent Product', 
        required=True, 
        ondelete='cascade', 
        index=True, 
        copy=False
    )

    product_id = fields.Many2one(
        'product.product', 
        string='Product', 
        domain=[('sale_ok', '=', True)], 
        change_default=True, 
        ondelete='restrict', 
        required=True
    )
    
    qty = fields.Integer(
        string='Quantity',
        required=True,
        readonly=False,
        default=1,
        help=False
    )