from openerp.osv import fields, osv
from openerp import api, fields, models, _
from openerp.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    is_product_bundle = fields.Boolean(
        string='Is Product Bundle',
        required=False,
        default=False,
        help="Specify if the product is pack bundle"
    )

    product_bundles = fields.One2many(
        'product.bundle', 
        'product_tmpl_id', 
        string='Product Template', 
        copy=True
    )

class ProductBundle(models.Model):
    _name = 'product.bundle'

    product_tmpl_id = fields.Many2one(
        'product.template', 
        string='Parent Template', 
        required=True, 
        ondelete='cascade', 
        select=True, 
        auto_join=True
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