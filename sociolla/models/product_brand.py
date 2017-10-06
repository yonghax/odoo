from openerp import api, fields, models, _

class ProductBrand(models.Model):
    _inherit = "product.brand"

    categ_id = fields.Many2one(
        string='Product Category',
        required=False,
        readonly=False,
        index=False,
        default=None,
        help="Select category for the current brand",
        comodel_name='product.category',
        domain=[('type','=','normal'), ('parent_id','=',False)],
    )