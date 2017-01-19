from openerp.osv import fields, osv
from openerp import api, fields, models, _
from openerp.exceptions import UserError
import openerp.addons.decimal_precision as dp

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

class swithcover_product(models.Model):
    _name = 'swithcover.product'
    _order = 'create_date DESC'
    
    date_done = fields.Datetime(
        string='Date Validated',
        required=False,
        readonly=True,
    )
    product_id = fields.Many2one(
        string='Switch-over Product',
        required=True,
        help=False,
        comodel_name='product.product',
        domain=[('is_product_switchover','=',True)],
        auto_join=True,
        ondelete='restrict',
        oldname='product_switchover'
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')

    notes = fields.Text(string='Note',required=True,states={'draft': [('readonly', False)]},readonly=True,)
    # company_id= fields.Many2one('res.company', 'Company', select=1, required=True, default=lambda self: self.env.user.company_id)
    # location_id= fields.Many2one('stock.location', 'Location', required=True, ondelete='restrict', readonly=True, select=True, auto_join=True,states={'draft': [('readonly', False)]})
    # package_id= fields.Many2one('stock.quant.package', 'Pack', select=True)
    # product_uom_id= fields.Many2one('product.uom', 'Product Unit of Measure', required=True)
    # prod_lot_id= fields.Many2one('stock.production.lot', 'Serial Number', domain="[('product_id','=',product_id)]")
    # partner_id= fields.Many2one('res.partner', 'Owner')

    # theoretical_qty = fields.Float(
    #     compute='_get_theoretical_qty', 
    #     digits_compute=dp.get_precision('Product Unit of Measure'),
    #     #store={'swithcover.product': (lambda self, cr, uid, ids, c={}: ids, ['location_id', 'product_switchover.switchover_product_mapping', 'package_id', 'product_uom_id', 'company_id', 'prod_lot_id', 'partner_id'], 20),},
    #     readonly=True, 
    #     string="Theoretical Quantity")

    qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)

    @api.onchange('product_id')
    def product_switchover_change(self):
        pass
        # if not self.product_id:
        #     return {'domain': {'product_uom': []}}
        
        # vals = {}
        # domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
        # if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
        #     vals['product_uom'] = self.product_id.uom_id
        #     vals['product_uom_qty'] = 1.0

        # product = self.product_id.with_context(
        #     lang=self.order_id.partner_id.lang,
        #     partner=self.order_id.partner_id.id,
        #     quantity=vals.get('product_uom_qty') or self.product_uom_qty,
        #     date=self.order_id.date_order,
        #     pricelist=self.order_id.pricelist_id.id,
        #     uom=self.product_uom.id
        # )

        # name = product.name_get()[0][1]
        # if product.description_sale:
        #     name += '\n' + product.description_sale
        # vals['name'] = name
        
    
    def action_done(self):
        pass

    def post_switchover(self):
        move_obj = self.pool.get('stock.move')
        vals = self.prepare_stock_move()

        move_obj.action_done(cr, uid, [x.id for x in inv.move_ids if x.state != 'done'], context=context)

    def prepare_stock_move(self):
        res = {
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'product_id': product.id,
            'procurement_id': proc_id,
            'product_uom': uom_id,
            'product_uom_qty': qty,
            'name': _('Extra Move: ') + name,
            'state': 'draft',
            'restrict_partner_id': op.owner_id.id,
            'group_id': picking.group_id.id,
        }

        return res
    
class ProductSupplierInfo(models.Model):
    _inherit='product.supplierinfo'
    
    discount = fields.Float(string='Disc(%)',default=0.0)
    