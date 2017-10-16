from openerp.osv import fields, osv
from openerp import api, fields, models, _
from openerp.exceptions import UserError
import openerp.addons.decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = "product.category"

    property_account_sales_discount_categ_id = fields.Many2one('account.account', company_dependent=True,
        string="Sales Discount",
        domain=[('deprecated', '=', False)],
        help="This account will be used for invoices to value sales discount.")
    property_account_sales_return_categ_id = fields.Many2one('account.account', company_dependent=True,
        string="Sales Return", 
        domain=[('deprecated', '=', False)],
        help="This account will be used for invoices to value sales return.")
    free_category = fields.Boolean(string=u'For Sample',)
        
class ProductTemplate(models.Model):
    _inherit = "product.template"

    property_account_sales_discount_id = fields.Many2one('account.account', company_dependent=True,
        string="Sales Discount",
        domain=[('deprecated', '=', False)],
        help="This account will be used for invoices instead of the default one to value sales discount for the current product.")
    property_account_sales_return_id = fields.Many2one('account.account', company_dependent=True,
        string="Sales Return", 
        domain=[('deprecated', '=', False)],
        help="This account will be used for invoices instead of the default one to value sales return for the current product.")
    
    is_product_switchover = fields.Boolean(string='Product Switchover')

    @api.model
    def _default_shop_id(self):
        return False
        user=self.env.user
        b2b = len(user.groups_id.filtered(lambda x: x.name=='B2B')) > 0
        b2c = len(user.groups_id.filtered(lambda x: x.name=='B2C')) > 0
        
        if b2c:
            return self.env['sale.shop'].search([('name', '=', 'sociolla.com')], limit=1)

        if b2b:
            return self.env['sale.shop'].search([('name', '=', 'Sociolla BO')], limit=1)

    shop_id = fields.Many2one(string='Shop',index=True,comodel_name='sale.shop')
    
    switchover_product_mapping = fields.Many2one(
        string='Switch-Over Product',
        comodel_name='product.template',
        domain=[('is_product_switchover', '=', False)],
        ondelete='cascade',
        auto_join=True
    )

    @api.multi
    def _get_asset_accounts(self):
        res = super(ProductTemplate, self)._get_asset_accounts()
        res['sales_discount'] = False
        res['sales_return'] = False
        return res

class product_template(osv.osv):
    _name = 'product.template'
    _inherit = 'product.template'

    @api.multi
    def _get_product_accounts(self):
        """ Add the sales discount, sales return related to product to the result of super()
        @return: dictionary which contains information regarding stock accounts and super (income+expense accounts)
        """
        accounts = super(product_template, self)._get_product_accounts()
        res = self._get_asset_accounts()
        accounts.update({
            'sales_discount': res['sales_discount'] or self.property_account_sales_discount_id or self.categ_id.property_account_sales_discount_categ_id,
            'sales_return': res['sales_return'] or self.property_account_sales_return_id or self.categ_id.property_account_sales_return_categ_id,
        })
        return accounts

    def _price_get(self, cr, uid, products, ptype='list_price', context=None):
        if context is None:
            context = {}

        res = {}
        product_uom_obj = self.pool.get('product.uom')
        for product in products:
            if ptype == 'list_price':
                res[product.id] = product['sale_price'] or product['list_price'] or 0.0
                res[product.id] += product._name == "product.product" and product.price_extra or 0.0
            elif ptype != 'standard_price':
                res[product.id] = product[ptype] or 0.0
            else:
                company_id = context.get('force_company') or product.env.user.company_id.id
                product = product.with_context(force_company=company_id)
                res[product.id] = product.sudo()[ptype]
            if 'uom' in context:
                uom = product.uom_id
                res[product.id] = product_uom_obj._compute_price(cr, uid,
                        uom.id, res[product.id], context['uom'])
            # Convert from current user company currency to asked one
            if 'currency_id' in context:
                # Take current user company currency.
                # This is right cause a field cannot be in more than one currency
                res[product.id] = self.pool.get('res.currency').compute(cr, uid, product.currency_id.id,
                    context['currency_id'], res[product.id], context=context)
        return res

class product_product(models.Model):
    _inherit = ['product.product']
    
    is_product_switchover = fields.Boolean(string='Product Switchover')
    
    switchover_product_mapping = fields.Many2one(
        string='Switch-Over Product',
        comodel_name='product.product',
        domain=[('is_product_switchover', '=', False)],
        ondelete='cascade',
        auto_join=True
    )

    sale_price = fields.Float(string='Sale Price')

class ProductSupplierInfo(models.Model):
    _inherit='product.supplierinfo'
    
    discount = fields.Float(string='Disc(%)',default=0.0)
    