from openerp import api, fields, models, _

class product_template(models.Model):
    _inherit = ['product.template']
    property_promotion_account_id = fields.Many2one(
        string=u'Promotion Account',
        domain=[('deprecated', '=', False)],
        comodel_name='account.account',
    )

class product_category(models.Model):
    _inherit = ['product.category']
    property_promotion_account_categ_id = fields.Many2one(
        string=u'Promotion Account',
        domain=[('deprecated', '=', False)],
        comodel_name='account.account',
    )

class product_product(models.Model):
    _inherit = ['product.product']
    bogo_promo = fields.Boolean(string=u'BOGO Promotion',)