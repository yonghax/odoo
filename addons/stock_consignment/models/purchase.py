from datetime import datetime

from openerp import api, fields, models, _, SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.float_utils import float_compare

import openerp.addons.decimal_precision as dp

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.multi
    def _add_supplier_to_product(self):
        super(PurchaseOrder, self)._add_supplier_to_product()

        for line in self.order_line:
            product = line.product_id

            if product.product_tmpl_id._get_purchase_type() == 'cons':
                prod_obj = self.pool.get('product.product')
                prod_obj.do_change_standard_price(product._cr,product._uid, product.ids, line.price_total / line.product_qty)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    owner_id = fields.Many2one(
        string='Owner ID',
        comodel_name='res.partner',
        domain=[('supplier', '=', True)],
        ondelete='cascade',
        auto_join=False
    )

    @api.constrains('product_id')
    def _validate_purchase_type(self):
        for line in self:
            if line.product_id.product_tmpl_id.categ_id.category_purchase_type and not line.product_id.product_tmpl_id._get_purchase_type():
                raise models.ValidationError('Purchase Type for brand ' + line.product_id.product_tmpl_id.product_brand_id.name + ' not define, please set the purchase type on Product Brand data.')

    @api.multi
    def _create_stock_moves(self, picking):
        moves = super(PurchaseOrderLine, self)._create_stock_moves(picking)
        for move in moves:
            if move.product_id.product_tmpl_id._get_purchase_type() == 'cons':
                move.owner_id = move.purchase_line_id.owner_id.id
                move.write({'owner_id': move.purchase_line_id.owner_id.id})

        return moves

    @api.onchange('product_id')
    def onchange_product_id(self):
        result = super(PurchaseOrderLine, self).onchange_product_id()
        
        if not self.product_id:
            return result

        product_tmpl_id = self.product_id.product_tmpl_id
        if product_tmpl_id._get_purchase_type() == 'cons':
            self.owner_id = self.order_id.partner_id.id