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
    active = fields.Boolean(string=u'Active', default=True,)
    sale_ok = fields.Boolean(string=u'Can be Sold', default=True,)
    purchase_ok = fields.Boolean(string=u'Can be Purchase', default=True,)
    business_type = fields.Selection(
        string=u'Business Type',
        default='b2b',
        selection=[('b2b', 'Business to Business'), ('b2c', 'Business to Consumer'), ('c2c', 'Consumer to Consumer')]
    )

    @api.multi
    def write(self, vals):
        res = super(ProductBrand, self).write(vals)
        if 'sale_ok' in vals or 'purchase_ok' in vals:
            for rec in self:
                rec.product_ids.write({'sale_ok': rec.sale_ok, 'purchase_ok': rec.purchase_ok})

        return res