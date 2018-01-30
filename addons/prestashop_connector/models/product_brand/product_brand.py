from openerp.osv import orm, fields

class product_brand(orm.Model):
    _inherit = 'product.brand'

    _columns = {
        'prestashop_bind_ids': fields.one2many(
            'prestashop.product.brand', 'openerp_id',
            string="PrestaShop Bindings"
        ),
    }

class prestashop_product_brand(orm.Model):
    _name='prestashop.product.brand'
    _inherit = 'prestashop.binding'
    _inherits = {'product.brand': 'openerp_id'}

    _columns = {
        'openerp_id': fields.many2one(
            'product.brand',
            string='Brand',
            required=True,
            ondelete='cascade'
        ),
    }