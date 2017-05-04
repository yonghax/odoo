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

    categoryEnum = {
        'BB': 'Bath & Body',
        'BT': 'Beauty Tools',
        'MU': 'Cosmetic',
        'FG': 'Fragrance',
        'HC': 'Haircare',
        'NL': 'Nailcare',
        'SC': 'Skincare',
    }
    
    @api.model
    def create(self, values):
        result = super(ProductBrand, self).create(values)
        
        for line in self:
            self.update_product_category(line.categ_id)

        return result

    
    @api.multi
    def write(self, values):
        result = super(ProductBrand, self).write(values)
        
        for line in self:
            self.update_product_category(line.categ_id)

        return result

    def update_product_category(self, product_category):
        categ_obj = self.env['product.category']

        for brand in self:
            for product in brand.product_ids:
                code = product.default_code

                strSplittedDash = code.split('-')
                strSplitted = strSplittedDash[0].split('.')

                if len(strSplitted) > 1:
                    categ = categ_obj.search(
                        [
                            ('parent_id', '=', product_category.id),
                            ('name', '=', self.categoryEnum[strSplitted[1]])
                        ]
                    )
                    if categ:
                        product.write({'categ_id': categ[0].id})
                    else:
                        raise models.ValidationException('Product ' + code + ' not valid, Please contact your administartor')